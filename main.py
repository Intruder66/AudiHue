"""
Created on 15.07.2017

@author: Intruder
"""
import csv
import json
import os
import sched
import subprocess
import sys
import time
import configparser
from builtins import str

import requests

if __name__ == "__main__":

    ##################### Begin of functions
    def readConfigFile():
        config = configparser.ConfigParser()
        config.read_file(open("AudiHue.cfg"))
        return config

    def assignValuesFromConfig(config):
        global bridge_ip, bridge_root, bridge_user, lights_url, user_url, foobar_ip, foobar_port
        bridge_ip = config['Hue Bridge']['bridge_ip']
        bridge_user = config['Hue Bridge']['bridge_user']
        foobar_ip = config['foobar2000 HTTP Control']['foobar_ip']
        foobar_port = config['foobar2000 HTTP Control']['foobar_port']

        bridge_root = "http://" + bridge_ip + "/api"
        user_url = bridge_root + "/" + bridge_user
        lights_url = user_url + "/lights"

    
    ##################### Hue Bridge control functions
    def j_dp(j):  # json debug printing to console
        print(json.dumps(j, indent=4))
    
    def authenticate():
        data = {"devicetype": bridge_user}
        r = requests.get(user_url, json=data)
        return r.json()

    def lightOn(light):
        data = {"on": True}
        r = requests.put(lights_url + "/" + light + "/state", json=data)
        return r.json()
    
    def lightSetXY(light, xy, bri, on=True, transitiontime="0"):
        """Set a light's XY, brightness, on/off value"""
        # Only send "on" value if set to False, to reduce delay
        data = {"bri": bri, "xy": xy, "transitiontime": transitiontime} if (on == True) else {"on": on, "bri": bri, "xy": xy}
        r = requests.put(lights_url + "/" + light + "/state", json=data)
        return r.json()
    
    def RGBtoXY(red, green, blue):
        """Convert color values from RGB to XY 
            https://developers.meethue.com/documentation/color-conversions-rgb-xy """
        
        red = 1 if (red == 0) else red
        green = 1 if (green == 0) else green
        blue = 1 if (blue == 0) else blue
        
        red = pow((red + 0.055) / (1.0 + 0.055), 2.4) if (red > 0.04045) else (red / 12.92)
        green = pow((green + 0.055) / (1.0 + 0.055), 2.4) if (green > 0.04045) else (green / 12.92)
        blue = pow((blue + 0.055) / (1.0 + 0.055), 2.4) if (blue > 0.04045) else (blue / 12.92)
        
        X = red * 0.664511 + green * 0.154324 + blue * 0.162028
        Y = red * 0.283881 + green * 0.668433 + blue * 0.047685
        Z = red * 0.000088 + green * 0.072310 + blue * 0.986039
        
        x = X / (X + Y + Z)
        y = Y / (X + Y + Z)
        
        xy = list()
        xy.append(x)
        xy.append(y)
        
        return xy
    
    ##################### File processing and lightshow functions
    def openTrack(filepath):
        # Open track in foobar2000 (or default associated program for file). Currently not used.
        if sys.platform.startswith("darwin"):
            subprocess.call(("open", filepath))
        elif os.name == "nt":
            os.startfile(filepath)
        elif os.name == "posix":
            subprocess.call(("xdg-open", filepath))
            
    def controlFoobar():
        requests.get("http://" + foobar_ip + ":" + foobar_port + "/default/?cmd=PlayOrPause")
        
    def processAEKeyframeFile(filepath, delim=";"):
        # Read file
        with open(filepath) as f:
            reader = csv.reader(f, delimiter=delim)
            content = list(reader)
            fps = content[2][2]
            keyframeTable = []
            
            # Find start of color key frame information
            # The keyword is the word that is looked for to get the start of the correct key frame lines
            keyword = "Frame"
            keywordOccurenceTable = [i for i, x in enumerate(content) if "Frame" in x]        
            line_ColorKeyframes_Start = keywordOccurenceTable[0] + 1
            line_BrightnessKeyframes_Start = keywordOccurenceTable[2] + 1               
            
            # Read and convert colors
            i = line_ColorKeyframes_Start
            line_ColorKeyframes_End = line_ColorKeyframes_Start + 1
            while i < line_ColorKeyframes_End:  
                # Check if next line is empty
                if content[i][1] != "":
                    # Append, structure: Time (frame number divided by fps), XY color value
                    keyframeTable.append([int(content[i][1]) / float(fps), RGBtoXY(float(content[i][3]), float(content[i][4]), float(content[i][5]))])
                    line_ColorKeyframes_End += 1
                i += 1
            
            # Read and convert brightness
            x = 0
            i = line_BrightnessKeyframes_Start
            line_BrightnessKeyframes_End = line_BrightnessKeyframes_Start + 1
            while i < line_BrightnessKeyframes_End:
                # Check if next line is empty
                if content[i][1] != "":
                    # Extend to existing table
                    keyframeTable[x].extend([(float(content[i][2]) * 2.54)]) 
                    line_BrightnessKeyframes_End += 1
                    x += 1
                i += 1    
    
            return keyframeTable
        
    def playLightshow(Lightshow):
        sch = sched.scheduler(time.time, time.sleep)
        sch.enter(0.1, 1, controlFoobar)
        # Iterate through all light channels
        for index, channel in enumerate(Lightshow):
            lightOn(str(index))
            # Iterate through all key frames per channel
            for row in channel:
                    # Schedule color and brightness keyframe
                    sch.enter(float(row[0]), 1, lightSetXY, argument=(str(index + 1), row[1], int(row[2])))
                    # sch.enter(float(row[0])+0.01, 2, print, argument=(str(index + 1), row[1], int(row[2]))) # Debugging
        sch.run()

    def composeChannels(channel01, channel02 = None, channel03 = None):
        channelComposition = []
        channelComposition.append(channel01)
        if channel02:
            channelComposition.append(channel02)
        if channel03:
            channelComposition.append(channel03)
        return channelComposition
            
    #def collectFiles(baseFilepath, numberOfChannels):
        
    ##################### End of functions

    assignValuesFromConfig(readConfigFile())
        
    authenticate()

    #lightshow01 = processAEKeyframeFile(os.path.join(r"C:\Users\Intruder\My Documents\LiClipse Workspace\AudiHue\test", "Servitude-AE-Keyframes-Left.csv"))
    #lightshow02 = processAEKeyframeFile(os.path.join(r"C:\Users\Intruder\My Documents\LiClipse Workspace\AudiHue\test", "Servitude-AE-Keyframes-Middle.csv"))
    #lightshow03 = processAEKeyframeFile(os.path.join(r"C:\Users\Intruder\My Documents\LiClipse Workspace\AudiHue\test", "Servitude-AE-Keyframes-Right.csv"))

    #lightshowComposition = composeChannels(lightshow03, lightshow01, lightshow02)
    # pprint(lightSetXY("1", [0.4573, 0.41], 253))
    #playLightshow(lightshowComposition)
    pass
