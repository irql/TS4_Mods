import os

import ui
import build_buy
import objects
import services
import sims4.commands
import sims4.log
from indexed_manager import ObjectIDError
from objects.gallery_tuning import ContentSource
from objects.object_enums import ItemLocation
from protocolbuffers import Consts_pb2

VERSION = 1.007

logger = sims4.log.Logger('IrqlInventoryCommands', default_owner='irql')

"""
NOTES:
  * If you transfer from household to sim inventory while at your business,
    then your business funds will increase by the amount that your sim's
    household inventory "sold" for, and this same amount will be subtracted
    from your actual household funds. (There is a bug where household and
    business funds are not properly separated if the sim is currently at
    the business location)
"""


class InventoryCommands:
    NOTIFICATION = ui.ui_dialog_notification.UiDialogNotification.TunableFactory()
    NOTIFICATION_TEXT = sims4.localization.TunableLocalizedStringFactory()

    def __init__(self, _connection):
        self._output = sims4.commands.CheatOutput(_connection)

    def try_to_run(self, command):
        try:
            getattr(self, command)()
        except BaseException as e:
            self._output('Failed to run "{}"'.format(command))
            for v in e.args:
                self._output("\t* " + v)
        pass

    def print_version(self):
        self._output('Version: {}'.format(str(VERSION)))

    def print_item_counts(self):
        active_sim_info = services.active_sim_info()
        self._show_dialog("Items in {} {}'s inventory: {}\n"
                          "Items in household inventory: {}".format(active_sim_info.first_name,
                                                                    active_sim_info.last_name,
                                                                    len(services.get_active_sim().inventory_component),
                                                                    len(build_buy.get_object_ids_in_household_inventory(
                                                                        services.active_household_id()))))

    def _show_dialog(self, text):
        loc_string = sims4.localization.LocalizationHelperTuning \
            .get_new_line_separated_strings(text, self.NOTIFICATION_TEXT())
        notification = self.NOTIFICATION(services.active_sim_info(),
                                         text=lambda *_: loc_string)
        notification.show_dialog()

    def move_sim_inventory_to_household(self):
        active_sim = services.get_active_sim()
        active_sim_info = services.active_sim_info()
        active_sim.inventory_component.push_items_to_household_inventory()
        self._show_dialog(
            "Moved all items in {} {}'s inventory to household inventory.".format(active_sim_info.first_name,
                                                                                  active_sim_info.last_name))

    def move_household_inventory_to_sim(self):
        logger.debug('START OF INVENTORY MIGRATION')
        active_sim = services.get_active_sim()
        household = active_sim.household
        object_ids = build_buy.get_object_ids_in_household_inventory(household.id)
        moved_object_count = 0
        if len(object_ids) > 0:
            total_cost = 0
            for object_id in object_ids:
                was_success, cost = self._move_item_from_household_to_sims_inventory(object_id, active_sim, household)
                total_cost += cost
                if was_success:
                    moved_object_count += 1
            # build_buy.remove_object_from_household_inventory() has the side-effect of bumping up
            # the current household funds as if we are performing a sale, when in reality we merely
            # want to move the object.
            #
            # Fortunately, if we immediately deduct the same value from the household funds, then
            # the UI doesn't even have a chance to show that anything changed.
            #
            if total_cost > 0:
                self._output('Subtracting ${} from household funds to offset sale'.format(total_cost))
                if not household.funds.try_remove(total_cost,
                                                  Consts_pb2.TELEMETRY_OBJECT_SELL,
                                                  sim=active_sim,
                                                  require_full_amount=False):
                    self._output('WARN: failed to subtract final amount')
            active_sim_info = services.active_sim_info()
            self._show_dialog("Moved {} items from household into {} {}'s inventory.".format(moved_object_count,
                                                                                             active_sim_info.first_name,
                                                                                             active_sim_info.last_name))
        else:
            self._show_dialog('No items found in household inventory.')

    def _move_item_from_household_to_sims_inventory(self, object_id, active_sim, household):
        new_object = self._copy_object(object_id, household.id)

        if new_object is None:
            logger.error('Failed to copy object {}', str(new_object))
            return False, 0

        inventory = active_sim.inventory_component
        if inventory.can_add(new_object):
            # We need to make a copy of the original object prior to moving it into the sims' inventory
            #
            if inventory.player_try_add_object(new_object):
                # We need to calculate how much money "remove_object_from_household_inventory" will
                # give us for removing this object so that we can subtract this amount later.
                #
                original_household_funds = household.funds.money
                if not build_buy.remove_object_from_household_inventory(object_id, household):
                    logger.error('FAILED: remove_object_from_household_inventory on object {}', str(new_object))
                    return False, 0  # don't destroy object if it was successfully added to sim inventory
                else:
                    simolean_delta = household.funds.money - original_household_funds
                    if simolean_delta == 0:
                        logger.warn('Defaulting to object cost of {}', new_object.base_value)
                        simolean_delta = new_object.base_value
                    return True, simolean_delta
            else:
                logger.error('FAILED: player_try_add_object on {}', str(new_object))
        # Destroy the copied object if we can't add it to sim inventory
        #
        new_object.destroy(cause='Removing orphaned object that cant be added to sim inventory')
        return False, 0

    def _copy_object(self, object_id, household_id):
        obj = None
        try:
            _, object_data = build_buy.get_definition_id_in_household_inventory(object_id, household_id)
            if object_data is None:
                raise ObjectIDError('object_data is None')
            logger.debug("===== OBJECT DATA =====\n{}", str(object_data))
            obj = objects.system.create_object(object_data.guid, obj_id=object_id, obj_state=object_data.state_index,
                                               loc_type=ItemLocation.SIM_INVENTORY,
                                               content_source=ContentSource.HOUSEHOLD_INVENTORY_PROXY)
            obj.attributes = object_data.SerializeToString()
            obj.set_household_owner_id(household_id)
        except ObjectIDError as exc:
            logger.error('Failed to create object: {}', exc)
        return obj


@sims4.commands.Command('irql.i', command_type=sims4.commands.CommandType.Live)
def dispatch_inventory_command(command: str, _connection=None):
    InventoryCommands(_connection).try_to_run(command)


@sims4.commands.Command('irql.i.move_household_inventory_to_sim', command_type=sims4.commands.CommandType.Live)
def dispatch_inventory_command_print_item_counts(_connection=None):
    InventoryCommands(_connection).try_to_run('move_household_inventory_to_sim')


@sims4.commands.Command('irql.i.move_sim_inventory_to_household', command_type=sims4.commands.CommandType.Live)
def dispatch_inventory_command_print_item_counts(_connection=None):
    InventoryCommands(_connection).try_to_run('move_sim_inventory_to_household')
