import os
from shutil import copytree, rmtree
from settings import mods_folder

root = os.path.join(os.path.dirname(os.path.realpath('__file__')), 'Scripts')
mod_name = os.path.basename(os.path.normpath(os.path.dirname(os.path.realpath('__file__'))))
mod_absolute_path = os.path.join(mods_folder, mod_name, 'Scripts')

# Remove existing mod dir if exists
rmtree(mod_absolute_path, ignore_errors=True)

# Copy sources to mod dir
copytree(root, mod_absolute_path)

# Remove pycache if exists
rmtree(os.path.join(mod_absolute_path, '__pycache__'), ignore_errors=True)
