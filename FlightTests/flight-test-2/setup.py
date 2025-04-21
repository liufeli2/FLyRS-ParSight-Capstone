from setuptools import setup

package_name = 'fl2'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jetson',
    maintainer_email='felicia.wanjin.liu@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'realsense_test = fl2.realsense_sys_node_unit:main',
            'vicon_test = fl2.vicon_sys_node_unit:main',
            'vision_test = fl2.visionpose_sys_node_unit:main',
            'full_test = fl2.handle_commands:main',
            'vicon = fl2.vicon_sys_node:main',
            'realsense = fl2.realsense_sys_node:main'
        ],
    },
)
