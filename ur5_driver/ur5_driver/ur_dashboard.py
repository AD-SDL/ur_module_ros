import socket
from time import sleep

class UR_DASHBOARD():
    def __init__(self, IP:str = "146.137.240.38", PORT: int = 29999):

        self.IP = IP
        self.port = PORT
        self.connection = None

        self.connect()

    def connect(self):
        """Create a socket"""
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.settimeout(5) # Socket will wait 10 seconds till it recieves the response
            self.connection.connect((self.IP,self.port))

        except Exception as err:
            print("UR dashboard could not establish connection")
            print(err)

    def disconnect(self):
        """Close the socket"""
        self.connection.close()

    def send_command(self, command, response_delay:float = 0.5):

        print(">> " + command)

        try:
            if not self.connection:
                self.connect()

            self.connection.sendall((command.encode("ascii") + b"\n")) #Check these to see if respond was received properly
            sleep(response_delay)
            response = self.connection.recv(4096).decode("utf-8")
                
            if response.find('Connected: Universal Robots Dashboard Server') != -1:
                print("Connected: Universal Robots Dashboard Server")
                response = response[45:]

            print("<< " + response[:-1])

            return response.strip()

        except Exception as err:
            print(err)

    def initialize(self):

        robot_mode = self.robot_mode()
        operation_mode = self.get_operational_mode()
        safety_status = self.safety_status()
        remote_control_status = self.is_in_remote_control()

        if safety_status.upper() == 'PROTECTIVE_STOP':
            print("Unlocking protective stop")
            self.unlock_protective_stop()

        elif safety_status.upper() != "NORMAL":   #safety_status.upper() != "ROBOT_EMERGENCY_STOP" or safety_status.upper() != "SYSTEM_EMERGENCY_STOP":
            print("Restarting safety")
            self.close_safety_popup()
            output = self.restart_safety()        

        if operation_mode.upper() == "MANUAL":
            print("Operation mode is currently set to MANUAL, switching to AUTOMATIC")
            self.set_operational_mode("automatic")

        if remote_control_status == False:
            print("Robot is not in remote control")
        
        if robot_mode.upper() == 'RUNNING' and safety_status.upper() == "NORMAL":
            print('Robot is initialized')
            return
        elif robot_mode.upper() == "POWER_OFF" or robot_mode.upper() == "BOOTING" or robot_mode.upper() == "POWER_ON" or robot_mode.upper() == "IDLE":
            print("Powering on the robot and releasing brakes")
            output = self.brake_release()

        return self.initialize()

    def robot_mode(self):
        """Return the robot mode"""
        output = self.send_command("robotmode")
        output = output.split(' ')
        return output[1]
        
    def quit(self):
        '''Closes connection to robot'''
        return self.send_command('quit')

    def shutdown(self):
        '''Shuts down and turns off robot and controller'''
        return self.send_command('shutdown')

    def power_on(self):
        '''Powers on the robot arm'''
        return self.send_command('power on')

    def power_off(self):
        '''Powers off the robot arm'''
        return self.send_command('power off')

    def brake_release(self):
        '''Releases the brakes'''
        output = self.send_command('brake release')
        sleep(20)
        return output

    def unlock_protective_stop(self):
        return self.send_command('unlock protective stop')

    def close_safety_popup(self):
        return self.send_command('close safety popup')

    def is_in_remote_control(self):
        return self.send_command('is in remote control')

    def restart_safety(self):
        output = self.send_command('restart safety')
        sleep(10)
        self.disconnect()
        self.connect()
        output2 = self.brake_release()
        return output
        
    def safety_status(self):
        output = self.send_command('safetystatus')
        output = output.split(' ')
        return output[1]

    def get_operational_mode(self):
        return self.send_command('get operational mode')

    def set_operational_mode(self, mode):
        return self.send_command('set operational mode ' + mode)

    def clear_operational_mode(self):
        return self.send_command('clear operational mode')

    def popup(self):
        return self.send_command('popup <popup-text>')

    def close_popup(self):
        return self.send_command('close popup')
    
    def load_program(self, program_path:str):
        return self.send_command("load " + program_path)
    
    def get_program_state(self):
        return self.send_command('programState')
    
    def get_loaded_program(self):
        return self.send_command('get loaded program ')
    
    def get_program_run_status(self):
        return self.send_command('running')
    
    def run_program(self):
        return self.send_command('play')
    
    def pause_program(self):
        return self.send_command('pause')
    
    def stop_program(self):
        return self.send_command('stop')


if __name__ == "__main__":
    robot = UR_DASHBOARD()
    # robot.robot_mode()
    # robot.close_popup()
<<<<<<< HEAD
    # robot.initialize()
=======
    robot.initialize()
>>>>>>> e45b54d9079386194dba265e7a6a5739fb44dfba
    # robot.send_command('clear operational mode')
    # robot.power_on()
    # robot.brake_release()
    # robot.power_off()
    # robot.brake_release()
    # robot.safety_status()
    # robot.quit()