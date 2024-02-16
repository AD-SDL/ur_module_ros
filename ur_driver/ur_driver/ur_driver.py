#!/usr/bin/env python3

import threading
import socket 

from multiprocessing.connection import wait
from time import sleep
from copy import deepcopy
import json
from math import radians, degrees

from ur_dashboard import UR_DASHBOARD
from ur_tools import *
from urx import Robot, RobotException

class Connection():
    """Connection to the UR robot to be shared within UR driver """
    def __init__(self,  hostname:str = "146.137.240.38", PORT: int = 29999) -> None:

        self.hostname = hostname
        self.PORT = PORT
        
        self.connection = None
        self.connect_ur()

    def connect_ur(self):
        """
        Description: Create conenction to the UR robot
        """

        for i in range(10):
            try:
                self.connection = Robot(self.hostname)

            except socket.error:
                print("Trying robot connection ...")
                sleep(10)

            else:
                print('Successful ur connection')
                break

    def disconnect_ur(self):
        """
        Description: Disconnects the socket connection with the UR robot
        """
        self.connection.close()
        print("Robot connection is closed.")

class UR():
    """
    This is the primary class for UR robots. 
    It integrates various interfaces to achieve comprehensive control, encompassing robot initialization via the UR dashboard, 
    robot motion using URx, and the management of robot end-effectors such as grippers, screwdrivers, electronic pipettes, and cameras."    
    """    
    def __init__(self, hostname:str = None, PORT: int = 29999):
        """Constructor for the UR class.
        :param hostname: Hostname or ip.
        :param port: Port.
        """

        if not hostname:
            raise TypeError("Hostname cannot be None Type!")
        
        # super().__init__(hostname=hostname, PORT=PORT)

        self.hostname = hostname
        self.PORT = PORT
        self.ur_dashboard = UR_DASHBOARD(hostname = self.hostname, PORT = self.PORT)
        self.ur = Connection(hostname = self.hostname, PORT = self.PORT)
        self.ur_connection = self.ur.connection
        self.ur_connection.set_tcp((0, 0, 0, 0, 0, 0))
        self.acceleration = 0.5
        self.velocity = 0.5
        self.speed_ms    = 0.750
        self.speed_rads  = 0.750
        self.accel_mss   = 1.200
        self.accel_radss = 1.200
        self.blend_radius_m = 0.001
        self.ref_frame = [0,0,0,0,0,0]
        self.robot_current_joint_angles = None
        self.get_movement_state()
        #TODO: get the information of what is the current tool attached to UR. Maybe keep the UR unattached after the tools were used? Run a senity check at the beginning to findout if a tool is connected 
    
    def get_movement_state(self):
        current_location = self.ur_connection.getj()
        current_location = [ '%.2f' % value for value in current_location] #rounding to 3 digits
        # print(current_location)
        if self.robot_current_joint_angles == current_location:
            movement_state = "READY"
        else:
            movement_state = "BUSY"

        self.robot_current_joint_angles = current_location

        return movement_state

    def home(self, home_location = None):
        """
        Description: Moves the robot to the home location.
        """
        print("Homing the robot...")
        if home_location:
            home_loc = home_location
        else:
            home_loc = [-1.355567757283346, -2.5413090191283167, 1.8447726408587855, -0.891581193809845, -1.5595606009112757, 3.3403327465057373]
        self.ur_connection.movej(home_loc,2,2)
        # sleep(3.5)

        print("Robot homed")
  
    def pick_tool(self, home, tool_loc, docking_axis = "y", payload = 0.12, tool_name:str = None):
        """
            Picks up a tool using the given tool location
        """
        self.ur_connection.set_payload(payload)
        wingman_tool = WMToolChangerController(tool_location = tool_loc, docking_axis = docking_axis, ur = self.ur_connection, tool = tool_name)
        self.home(home)
        wingman_tool.pick_tool()
        self.home(home)    

    def place_tool(self, home, tool_loc, docking_axis = "y", tool_name:str = None):
        """
            Picks up a tool using the given tool location
        """
        wingman_tool = WMToolChangerController(tool_location = tool_loc, docking_axis = docking_axis, ur = self.ur_connection, tool = tool_name)
        self.home(home)
        wingman_tool.place_tool()
        self.home(home)  

    def gripper_transfer(self, home:list = None, source: list = None, target: list = None, source_approach_axis:str = None, target_approach_axis:str = None, source_approach_distance: float = None, target_approach_distance: float = None, gripper_open:int = None, gripper_close:int = None) -> None:
        '''
        Make a transfer using the finger gripper. This function uses linear motions to perform the pick and place movements.
        ''' 
        if not source or not target:
            raise Exception("Please provide both the source and target loactions to make a transfer")
        
        self.home(home)
        
        try:
            gripper_controller = FingerGripperController(hostname = self.hostname, ur = self.ur_connection)
            gripper_controller.connect_gripper()

            if gripper_open:
                gripper_controller.gripper_open = gripper_open
            if gripper_close:
                gripper_controller.gripper_close = gripper_close

            gripper_controller.transfer(home = home, source = source, target = target,source_approach_axis = source_approach_axis, target_approach_axis = target_approach_axis, source_approach_distance = source_approach_distance, target_approach_distance = target_approach_distance)
            print('Finished transfer')
            gripper_controller.disconnect_gripper()

        except Exception as err:
            print(err)

        finally:
            gripper_controller.disconnect_gripper()
            self.home(home)

    def gripper_screw_transfer(self, home:list = None, target:list = None, screwdriver_loc: list = None, screw_loc: list = None, screw_time:float = 9, gripper_open:int = None, gripper_close:int = None) -> None:
        """
        Using custom made screwdriving solution.
        """

        self.home(home)

        try:
            gripper_controller = FingerGripperController(hostname = self.hostname, ur = self.ur_connection)
            gripper_controller.connect_gripper()

            if gripper_open:
                gripper_controller.gripper_open = gripper_open
            if gripper_close:
                gripper_controller.gripper_close = gripper_close

            gripper_controller.pick(pick_goal = screwdriver_loc)

            # # Pick screw
            self.home(home)
            above_goal = deepcopy(screw_loc)
            above_goal[2] += 0.06
            self.ur_connection.movel(above_goal, self.acceleration, self.velocity)
            self.ur_connection.movel(screw_loc, 0.2, 0.2)
            self.ur_connection.movel(above_goal, self.acceleration, self.velocity)

            # Move to the target location
            above_target = deepcopy(target)
            above_target[2] += 0.03
            self.ur_connection.movel(above_target, self.acceleration, self.velocity)
            self.ur_connection.movel(target, 0.2, 0.2)

            target_pose = [0,0,0.00021,0,0,3.14] #Setting the screw drive motion
            print("Screwing down")

            self.ur_connection.speedl_tool(target_pose,2, screw_time) # This will perform screw driving motion for defined number of seconds
            sleep(screw_time+0.5)

            self.ur_connection.translate_tool([0,0,-0.03],0.5,0.5)
            self.home(home)

            gripper_controller.place(place_goal=hex_key)
            self.home(home)

        except Exception as err:
            print(err)

        finally:
            gripper_controller.disconnect_gripper()

    def gripper_unscrew(self, home:list = None, target:list = None, screwdriver_loc: list = None, screw_loc: list = None, screw_time:float = 10, gripper_open:int = None, gripper_close:int = None) -> None:
        """Perform unscrewing"""
        pass
    
    def remove_cap(self, home:list = None, source:list = None, target:list = None, gripper_open:int = None, gripper_close:int = None) -> None:
        """Removes the cap"""
        self.home(home)

        try:
            gripper_controller = FingerGripperController(hostname = self.hostname, ur = self.ur_connection)
            gripper_controller.connect_gripper()
            if gripper_open:
                gripper_controller.gripper_open = gripper_open
            if gripper_close:
                gripper_controller.gripper_close = gripper_close

            gripper_controller.open_gripper()
            above_goal = deepcopy(source)
            above_goal[2] += 0.06
            self.ur_connection.movel(above_goal, self.acceleration, self.velocity)
            self.ur_connection.movel(source, 0.2, 0.2)

            gripper_controller.close_gripper()
            
            target_pose = [0,0,-0.001,0,0,-3.14] #Setting the screw drive motion
            print("Removing cap")
            screw_time = 7
            self.ur_connection.speedl_tool(target_pose,2, screw_time) # This will perform screw driving motion for defined number of seconds
            sleep(screw_time+0.5)
            self.ur_connection.translate_tool([0,0,-0.03],0.5,0.5)
            
            self.home(home)
            gripper_controller.place(place_goal=target)
            self.home(home)

        except Exception as err:
            print(err)

    def place_cap(self, home:list = None, source:list = None, target:list = None, gripper_open:int = None, gripper_close:int = None) -> None:
        """Places the cap back"""
        self.home(home)

        try:
            gripper_controller = FingerGripperController(hostname = self.hostname, ur = self.ur_connection)
            gripper_controller.connect_gripper()
            if gripper_open:
                gripper_controller.gripper_open = gripper_open
            if gripper_close:
                gripper_controller.gripper_close = gripper_close

            gripper_controller.pick(pick_goal= source)
            self.home(home)

            above_goal = deepcopy(target)
            above_goal[2] += 0.06
            self.ur_connection.movel(above_goal, self.acceleration, self.velocity)
            self.ur_connection.movel(target, 0.1, 0.1)

            # gripper_controller.close_gripper()
            
            target_pose = [0,0,0.0001,0,0,3.14] #Setting the screw drive motion
            print("Placing cap")
            screw_time = 6
            self.ur_connection.speedl_tool(target_pose,2, screw_time) # This will perform screw driving motion for defined number of seconds
            sleep(screw_time+0.5)

            gripper_controller.open_gripper()
            self.ur_connection.translate_tool([0,0,-0.03],0.5,0.5)
            self.home(home)


        except Exception as err:
            print(err)

    def pick_and_flip_object(self, home:list = None, target: list = None, approach_axis:str = None, target_approach_distance: float = None, gripper_open:int = None, gripper_close:int = None) -> None:
        '''
        Pick an object then flips it and puts it back to the same location
        '''

        self.home(home)

        try:
            gripper_controller = FingerGripperController(hostname = self.hostname, ur = self.ur_connection)
            gripper_controller.connect_gripper()

            if gripper_open:
                gripper_controller.gripper_open = gripper_open
            if gripper_close:
                gripper_controller.gripper_close = gripper_close

            gripper_controller.pick(pick_goal = target, approach_axis = approach_axis)
    
            cur_j = self.ur_connection.getj()
            rotate_j = cur_j 
            rotate_j[5] += radians(180) 
            robot.ur_connection.movej(rotate_j,0.6,0.6)

            cur_l = self.ur_connection.getl()
            target[3] = cur_l[3]
            target[4] = cur_l[4]
            target[5] = cur_l[5]
            
            gripper_controller.place(place_goal = target, approach_axis = approach_axis)
            self.home(home)

        except Exception as er:
            print(er)
        finally:
            gripper_controller.disconnect_gripper()

    def robotiq_screwdriver_transfer(self, home:list = None, source: list = None, target: list = None, source_approach_axis:str = None, target_approach_axis:str = None, source_approach_distance: float = None, target_approach_distance: float = None) -> None:
        '''
        Make a screw transfer using the screwdriver. This function uses linear motions to perform the pick and place movements.
        ''' 

        self.home(home)

        try:
            sr = ScrewdriverController(hostname = self.hostname, ur = self.ur_connection, ur_dashboard = self.ur_dashboard)
            sr.screwdriver.activate_screwdriver()
            sr.transfer(source=source, target=target, source_approach_axis=source_approach_axis, target_approach_axis = target_approach_axis, source_approach_dist=source_approach_distance, target_approach_dist=target_approach_distance)
            sr.screwdriver.disconnect()
        except Exception as err:
            print(err)
        
        self.home(home)

    def pipette_transfer(self, home:list = None,  tip_loc: list = None, tip_trash:list = None, source:list = None, target:list = None, volume:int = 10) -> None:
        '''a
        Make a liquid transfer using the pipette. This function uses linear motions to perform the pick and place movements.
        ''' 
        if not tip_loc or not source:
            raise Exception("Please provide both the source and target loactions to make a transfer")
        
        try:
            pipette = TricontinentPipetteController(hostname = self.hostname, ur = self.ur_connection, pipette_ip=self.hostname)
            pipette.connect_pipette()
            pipette.pick_tip(tip_loc=tip_loc)
            self.home(home)
            pipette.transfer_sample(home = home, sample_aspirate=source, sample_dispense=target, vol = volume)
            pipette.eject_tip(eject_tip_loc=tip_trash,approach_axis="y")
            pipette.disconnect_pipette()
            print("Disconnecting from the pipette")
        except Exception as err:
            print(err)
        finally:

            # self.home(home)
            pass
   
    def run_droplet(self, home, tip_loc, sample_loc, droplet_loc, tip_trash):
        """Create droplet"""

        pipette = OTPipetteController(ur_connection = self.ur_connection, IP = self.hostname)
        pipette.connect_pipette()

        self.home(home)
        pipette.pick_tip(tip_loc=tip_loc)
        pipette.transfer_sample(sample_loc=sample_loc)
        self.home(home)
        pipette.create_droplet(droplet_loc=droplet_loc)
        self.home(home)
        pipette.empty_tip(sample_loc=sample_loc)     
        pipette.eject_tip(eject_tip_loc=tip_trash)
        self.home(home)
        pipette.disconnect_pipette()
        self.ur_connection.set_tool_communication

    def run_urp_program(self, transfer_file_path:str = None, program_name: str = None):

        """Transfers the urp programs onto the polyscope and initiates them"""
        if not program_name:
            raise ValueError("Provide program name!")
        
        ur_program_path = "/programs/" + program_name 

        if transfer_file_path:
            self.ur_dashboard.transfer_program(local_path = transfer_file_path, ur_path = ur_program_path)
            sleep(2)

        self.ur_dashboard.load_program(program_path = ur_program_path)
        sleep(2)
        self.ur_dashboard.run_program()
        sleep(5)
        
        print("Running the URP program: ", program_name)
        time_elapsed = 0
        program_err = ""
        
        program_status = "BUSY"
        ready_status_count = 0
        while program_status == "BUSY":
            if self.get_movement_state() == "READY":
                ready_status_count += 1
                if ready_status_count >=6:
                    program_status = "READY"
            else:
                ready_status_count = 0
            sleep(3)

        program_log = {"output_code":"0", "output_msg": "Successfully finished " + program_name, "output_log": "seconds_elapsed:" + str(time_elapsed)}

        return program_log
    
if __name__ == "__main__":

    pos1= [-0.22575, -0.65792, 0.39271, 2.216, 2.196, -0.043]
    pos2= [0.22575, -0.65792, 0.39271, 2.216, 2.196, -0.043]
    robot = UR(hostname="164.54.116.129")
    # robot = UR(hostname="192.168.1.102")

    home = [0.5431541204452515, -1.693524023095602, -0.7301170229911804, -2.2898713550963343, 1.567720651626587, -1.0230830351458948]
    pipette_loc = [0.21285670041158733, 0.1548897634390196, 0.005543999069077835, 3.137978068966478, -0.009313836267512065, -0.0008972976992386885]
    handE_loc = [0.3131286590368134, 0.15480163498252172, 0.005543999069077835, 3.137978068966478, -0.009313836267512065, -0.0008972976992386885]
    screwdriver_loc = [0.43804370307762014, 0.15513117190281586, 0.006677533813616729, 3.137978068966478, -0.009313836267512065, -0.0008972976992386885]
    
    tip1 = [0.04314792894103472, -0.2860322742006418, 0.2280902599833372, 3.1380017093793624, -0.00934365687097245, -0.0006742913527073343]
    sample = [0.46141141854542533, -0.060288367363232544, 0.25108778472947074, 3.1380721475655364, -0.009380578809401673, -0.0005480714914954698]
    sample_dispense = [0.3171082280819746, -0.2850972337811901, 0.3411125132555506, 3.1379895509880757, -0.009383853947478633, -0.0007087863735219047]
    vial_cap = [0.46318998963189156, -0.0618242346521575, 0.22044247577669074, 3.1380871312109466, -0.009283145361593024, -0.0008304449494246685]
    vial_cap_holder = [0.3496362594442045, -0.19833129786349898, 0.21851956360142491, 3.1380370691898447, -0.00907338154155439, -0.0006817652068428923]
    tip_trash = [0.2584365150735084, -0.29839447002022784, 0.26381819707970183, 3.1380107495494363, -0.009257765762271986, -0.0005604922095049701]

    cell_screw = [0.28742456966563107, -0.2863121497438419, 0.3180272525328063, 3.1380212198586985, -0.009448362088018303, -0.0006280218794236092]
    cell_screw2 = [0.28802533355775894, -0.3111315576736609, 0.3180272525328063, 3.138055908188219, -0.009412952001123928, -0.0007497956393069067]

    # screw_holder = [0.21876722334540147, -0.27273358502932915, 0.39525473397805677, 3.0390618278038524, -0.7398330220514875, 0.016498425988567388]
    hex_key = [0.40061621427107863, -0.19851389684726614, 0.2185475541919895, 3.1374987322951102, -0.009368331063787221, -0.0007768712432287358]
    cell_holder = [0.43785674873555014, -0.1363043381282072, 0.21998506102422555, 3.1380513355558466, -0.009323037734842953, -0.0006690858747472434]
    assembly_deck = [0.3174903285108201, -0.08258211007606345, 0.11525282484663647, 1.2274734115134542, 1.190534780943193, -1.1813375188608897]
    assembly_above = [0.31914521296697795, -0.2855210106568889, 0.3477093639368639, 3.1380580674341614, -0.009396149170921641, -0.0006625851593942707]
    test_loc = [0.30364466226740844, -0.1243275644148994, 0.2844145579322907, 3.1380384242791366, -0.009336265404641286, -0.0007377624513656736]

    # robot.home(home)
    # print(robot.ur_connection.getl())

    # robot.pick_tool(home, pipette_loc,payload=1.2)

    
    # SCREWDRIVING ---------------------------
    # robot.pick_tool(home, screwdriver_loc,payload=3)
    # robot.screwdriver_transfer(home=home,source=hex_key,target=hex_key, source_approach_distance=0.04)
    # robot.place_tool(home,screwdriver_loc)
    
    # ----------------------------------------
    # CELL ASSEMBLY

    # Put a cell into assamply and instal cap on one side
    robot.pick_tool(home, handE_loc,payload=1.2)
    robot.gripper_transfer(home = home, source = cell_holder, target = assembly_deck, source_approach_axis="z", target_approach_axis="y", gripper_open = 190, gripper_close = 240)
    robot.gripper_screw_transfer(home=home,screwdriver_loc=hex_key,screw_loc=cell_screw,target=assembly_above,gripper_open=120,gripper_close=200,screw_time=10)
    robot.pick_and_flip_object(home=home,target=assembly_deck,approach_axis="y",gripper_open=190,gripper_close=240)
    robot.remove_cap(home=home,source=vial_cap,target=vial_cap_holder,gripper_open=120, gripper_close=200)
    robot.place_tool(home,tool_loc=handE_loc)

    # Transfer sample using pipette  
    robot.pick_tool(home,tool_loc=pipette_loc,payload=1.2)
    robot.pipette_transfer(home=home,tip_loc=tip1, tip_trash=tip_trash, source=sample, target=sample_dispense, volume=9)
    robot.place_tool(home,tool_loc=pipette_loc)
    
    # Install cap on the other side of the cell
    robot.pick_tool(home, handE_loc,payload=1.2)
    robot.place_cap(home=home,source=vial_cap_holder,target=vial_cap,gripper_open=120, gripper_close=200)
    robot.gripper_screw_transfer(home=home,screwdriver_loc=hex_key,screw_loc=cell_screw2,target=assembly_above,gripper_open=120,gripper_close=200,screw_time=10)
    robot.gripper_transfer(home = home, source = assembly_deck, target = cell_holder, source_approach_axis="y", target_approach_axis="z", gripper_open = 190, gripper_close = 240)
    robot.place_tool(home, handE_loc)
    robot.ur.disconnect_ur()
    





