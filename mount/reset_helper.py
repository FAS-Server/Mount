import os
import shutil

from .utils import logger


class ResetHelper:
    @staticmethod
    def reset(slot_path, reset_path, reset_type):
        reserve_dirs = ['playerdata', 'advancements', 'stats']
        worlds = ['world', 'world_nether', 'world_the_end']
        reset_worlds = filter(lambda x: os.path.isdir(x),
            map(lambda x: os.path.join(slot_path, reset_path, x), worlds))
        curr_worlds = filter(lambda x: os.path.isdir(x),
            map(lambda x: os.path.join(slot_path, x), worlds))

        # reset main world (maybe the only world)
        curr_main_world = os.path.join(slot_path, 'world')
        reset_main_world = os.path.join(slot_path, reset_path, 'world')
        if curr_main_world not in curr_worlds:
            pass
        elif reset_type == 'region':
            dirs = os.listdir(curr_main_world)
            for i in map(lambda x: os.path.join(curr_main_world, x),
                filter(lambda x: x not in reserve_dirs, dirs)):
                logger().info(f'Deleting world/{os.path.basename(i)}...')
                if os.path.isdir(i):
                    shutil.rmtree(i)
                else:
                    os.remove(i)
        elif reset_type == 'full':
            logger().info('Deleting the whole world/')
            shutil.rmtree(curr_main_world)

        if reset_main_world not in reset_worlds:
            logger().info('No need to reset world/')
        elif reset_type == 'region':
            dirs = os.listdir(reset_main_world)
            for i in map(lambda x: os.path.join(reset_main_world, x),
                filter(lambda x: x not in reserve_dirs, dirs)):
                logger().info(f'Resetting world/{os.path.basename(i)}')
                if os.path.isdir(i):
                    shutil.copytree(i, os.path.join(curr_main_world, os.path.basename(i)))
                else:
                    shutil.copy(i, os.path.join(curr_main_world, os.path.basename(i)))
        elif reset_type == 'full':
            logger().info('Resetting the whole world/')
            shutil.copytree(reset_main_world, curr_main_world)

        for i in worlds[1:]:
            dir1 = os.path.join(slot_path, i)
            dir2 = os.path.join(slot_path, reset_path, i)
            if dir1 in curr_worlds:
                logger().info(f'Deleting {i}')
                shutil.rmtree(dir1)
            if dir2 in reset_worlds:
                logger().info(f'Resetting {i}')
                shutil.copytree(dir2, dir1)