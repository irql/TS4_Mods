import sims4.commands
import services
import build_buy
import objects

from indexed_manager import ObjectIDError
from objects.object_enums import ItemLocation
from protocolbuffers import Consts_pb2


@sims4.commands.Command('irql.debug', command_type=sims4.commands.CommandType.Live)
def debug(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    output('Current sim inventory items: {}'.format(len(services.get_active_sim().inventory_component)))
    output('Items in household inventory: {}'.format(
        len(build_buy.get_object_ids_in_household_inventory(services.active_household_id()))))


@sims4.commands.Command('irql.move_household_inventory_to_sim', command_type=sims4.commands.CommandType.Live)
def move_household_inventory_to_sim(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    household = services.active_household()
    object_ids = build_buy.get_object_ids_in_household_inventory(household.id)
    if len(object_ids) > 0:
        object_manager = services.object_manager()
        active_sim = services.get_active_sim()
        active_sim_info = services.active_sim_info()
        output(
            "Moving {} items from household into {} {}'s inventory.".format(len(object_ids), active_sim_info.first_name,
                                                                            active_sim_info.last_name))
        for id in object_ids:
            _move_item_from_household_to_sims_inventory(output, id, object_manager, active_sim, household)
    else:
        output("No items found in household inventory.")


def _move_item_from_household_to_sims_inventory(output, object_id, object_manager, active_sim, household):
    object = _copy_object(output, object_id, household.id)
    if object is None:
        output('Failed to copy object')
        return False
    inventory = active_sim.inventory_component
    if inventory.can_add(object):
        # We need to make a copy of the original object prior to moving it into the sims' inventory
        #
        if inventory.player_try_add_object(object):
            if build_buy.object_exists_in_household_inventory(object_id, household.id):
                if not build_buy.remove_object_from_household_inventory(object_id, household):
                    output('FAILED: remove_object_from_household_inventory')
                    return False  # don't destroy object if it was successfully added to sim inventory
                else:
                    # build_buy.remove_object_from_household_inventory() has the side-effect of bumping up
                    # the current household funds as if we are performing a sale, when in reality we merely
                    # want to move the object.
                    #
                    # Fortunately, if we immediately deduct the same value from the household funds, then
                    # the UI doesn't even have a change to show that anything changed.
                    #
                    if not household.funds.try_remove(object.current_value,
                                                      Consts_pb2.TELEMETRY_HOUSEHOLD_TRANSFER_LOSS, sim=active_sim,
                                                      require_full_amount=False):
                        output('WARN: failed to subtract amount {}'.format(object.current_value))
                    return True
        else:
            output('FAILED: player_try_add_object')
    # Destroy the copied object if we can't add it to sim inventory
    #
    object.destroy(cause='Removing orphaned object that cant be added to sim inventory')
    return False


def _copy_object(output, object_id, household_id):
    obj = None
    try:
        _, object_data = build_buy.get_definition_id_in_household_inventory(object_id, household_id)
        obj = objects.system.create_object(object_data.guid, obj_id=object_id, obj_state=object_data.state_index,
                                           loc_type=ItemLocation.SIM_INVENTORY)
        obj.set_household_owner_id(household_id)
    except ObjectIDError as exc:
        output('Failed to create object: {}'.format(exc))
    return obj
