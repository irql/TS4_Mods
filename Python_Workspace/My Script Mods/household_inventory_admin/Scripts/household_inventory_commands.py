import logging
import os

import build_buy
import objects
import services
import sims4.commands
from indexed_manager import ObjectIDError
from objects.gallery_tuning import ContentSource
from objects.object_enums import ItemLocation
from protocolbuffers import Consts_pb2

VERSION = 1.005

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
    _log_level = logging.INFO
    _log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    def __init__(self, _connection):
        self._output = sims4.commands.CheatOutput(_connection)
        self._logger = self._setup_logger()

    def try_to_run(self, command):
        try:
            getattr(self, command)()
        except BaseException as e:
            self._output('Failed to run "{}"'.format(command))
            for v in e.args:
                self._output("\t* " + v)
        pass

    def _log_file_name(self):
        return '{}.{}.log'.format(self.__class__.__name__, str(self._log_level))

    def _log_file_path(self):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', self._log_file_name())

    def _setup_logger(self):
        logger = logging.getLogger('Irql' + self.__class__.__name__)
        if not logger.hasHandlers():
            logger.setLevel(self._log_level)
            fh = logging.FileHandler(self._log_file_path(), mode='a', encoding='utf-8')
            fh.setLevel(self._log_level)
            formatter = logging.Formatter(self._log_format)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        return logger

    def print_version(self):
        self._output('Version: {}'.format(str(VERSION)))

    def print_item_counts(self):
        active_sim_info = services.active_sim_info()
        self._output("Items in {} {}'s inventory: {}".format(active_sim_info.first_name, active_sim_info.last_name,
                                                             len(services.get_active_sim().inventory_component)))
        self._output('Items in household inventory: {}'.format(
            len(build_buy.get_object_ids_in_household_inventory(services.active_household_id()))))

    def move_sim_inventory_to_household(self):
        active_sim = services.get_active_sim()
        active_sim_info = services.active_sim_info()
        self._output("Moving all items in {} {}'s inventory to household inventory.".format(active_sim_info.first_name,
                                                                                            active_sim_info.last_name))
        active_sim.inventory_component.push_items_to_household_inventory()

    def move_household_inventory_to_sim(self):
        self._logger.debug('START OF INVENTORY MIGRATION')
        active_sim = services.get_active_sim()
        household = active_sim.household  # services.active_household()
        object_ids = build_buy.get_object_ids_in_household_inventory(household.id)
        if len(object_ids) > 0:
            active_sim_info = services.active_sim_info()
            self._output("Moving {} items from household into {} {}'s inventory.".format(len(object_ids),
                                                                                         active_sim_info.first_name,
                                                                                         active_sim_info.last_name))
            total_cost = 0
            for object_id in object_ids:
                _, cost = self._move_item_from_household_to_sims_inventory(object_id, active_sim, household)
                total_cost += cost
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
        else:
            self._output('No items found in household inventory.')

    def _move_item_from_household_to_sims_inventory(self, object_id, active_sim, household):
        new_object = self._copy_object(object_id, household.id)

        if new_object is None:
            self._logger.error('Failed to copy object {}'.format(str(new_object)))
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
                    self._logger.error(
                        'FAILED: remove_object_from_household_inventory on object {}'.format(str(new_object)))
                    return False, 0  # don't destroy object if it was successfully added to sim inventory
                else:
                    simolean_delta = household.funds.money - original_household_funds
                    if simolean_delta == 0:
                        self._logger.warning('Defaulting to object cost of {}', new_object.base_value)
                        simolean_delta = new_object.base_value
                    return True, simolean_delta
            else:
                self._logger.error('FAILED: player_try_add_object on {}'.format(str(new_object)))
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
            self._logger.debug("===== OBJECT DATA =====\n{}".format(str(object_data)))
            obj = objects.system.create_object(object_data.guid, obj_id=object_id, obj_state=object_data.state_index,
                                               loc_type=ItemLocation.SIM_INVENTORY,
                                               content_source=ContentSource.HOUSEHOLD_INVENTORY_PROXY)
            obj.attributes = object_data.SerializeToString()
            obj.set_household_owner_id(household_id)
        except ObjectIDError as exc:
            self._logger.error('Failed to create object: {}'.format(exc))
        return obj


@sims4.commands.Command('irql.v', command_type=sims4.commands.CommandType.Live)
def version(_connection=None):
    InventoryCommands(_connection).try_to_run('print_version')


@sims4.commands.Command('irql.debug', command_type=sims4.commands.CommandType.Live)
def debug(_connection=None):
    InventoryCommands(_connection).try_to_run('print_item_counts')


@sims4.commands.Command('irql.move_sim_inventory_to_household', command_type=sims4.commands.CommandType.Live)
def move_sim_inventory_to_household(_connection=None):
    InventoryCommands(_connection).try_to_run('move_sim_inventory_to_household')


@sims4.commands.Command('irql.move_household_inventory_to_sim', command_type=sims4.commands.CommandType.Live)
def move_household_inventory_to_sim(_connection=None):
    InventoryCommands(_connection).try_to_run('move_household_inventory_to_sim')
