import os

creator_name = 'irql'
mods_folder = os.path.expanduser(
    os.path.join('~', 'Documents', 'Electronic Arts', 'The Sims 4', 'Mods')
)

# Path for Steam installation
# - C:\Program Files (x86)\Steam\steamapps\common\The Sims 4\Data\Simulation\Gameplay
# 
game_folder = os.path.join('C:', os.sep, 'Program Files (x86)', 'Steam', 'steamapps', 'common', 'The Sims 4')

# Path for Origin native installation
# - C:\Program Files (x86)\Origin Games\The Sims 4
#
# game_folder = os.path.join('C:', os.sep, 'Program Files (x86)', 'Origin Games', 'The Sims 4')

