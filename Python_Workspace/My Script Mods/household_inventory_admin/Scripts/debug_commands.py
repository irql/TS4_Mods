import sims4.commands
import sims4.reload
import os.path


@sims4.commands.Command('irql.r', command_type=sims4.commands.CommandType.Live)
def reload_submodules(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    base_dir = os.path.dirname(os.path.realpath(__file__))
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            try:
                sims4.reload.reload_file(os.path.join(root, file))
            except BaseException as e:
                output('Failed to load {}:'.format(file))
                for v in e.args:
                    output(v)
            output('Reloaded: ' + file)
    output('Done reloading.')
