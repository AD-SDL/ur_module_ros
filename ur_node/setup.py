from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'ur_node'

setup(
    version='0.0.0',
    packages= find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml.py')),

    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Doga Ozgulbas',
    maintainer_email='dozgulbas@anl.gov',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ur_action_server = ur_node.ur_action_server:main',

        ],
    },
)