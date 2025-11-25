import re
import ast
from xml.sax import parse

import requests
import time

'''
version info (shouldn't matter that much)
certifi==2025.11.12
charset-normalizer==3.4.4
idna==3.11
requests==2.32.5
urllib3==2.5.0
'''

#Printer IP
MOONRAKER_URL = "http://10.3.141.1/printer/gcode/script"

#SET THESE ACCORDING TO PRINTER AND BOARD SPECS
#Provide correct offset of printbed to placement board
X_ORIGIN_PLACEMENT = 107.50
Y_ORIGIN_PLACEMENT = 190
X_ORIGIN_PICKUP = 156.5
Y_ORIGIN_PICKUP = 141.5
PLACE_HEIGHT = 14
PICKUP_HEIGHT = 14
PASSIVE_HEIGHT = 45

#pickup trackers, do not change these
col_dict = {'R': 0, 'C': 2, 'L': 4, 'LED': 6, 'W6': 8}
len_dict = {'R': 6, 'C': 6, 'L': 6, 'LED': 6, 'W6': 6}
wires_used = {'W6': 0}

#GCODE To dump
GCODE = ''

'''
input is:
components:
R1 {'anchor': (1, 10), 'body': [(1, 10), (2, 10), (3, 10), (4, 10), (5, 10), (6, 10)], 'pins': [(1, 10), (6, 10)], 'nets': ('V+', 'N1')}
C1 {'anchor': (3, 1), 'body': [(3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (8, 1)], 'pins': [(3, 1), (8, 1)], 'nets': ('N1', 'N2')}
L1 {'anchor': (5, 0), 'body': [(5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0)], 'pins': [(5, 0), (10, 0)], 'nets': ('N2', 'N3')}
LED {'anchor': (7, 1), 'body': [(7, 1), (8, 1), (9, 1), (10, 1), (11, 1), (12, 1)], 'pins': [(7, 1), (12, 1)], 'nets': ('N3', 'GND')}

wires:
{'net': 'WIRE', 'holes': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]}

TERMS:
anchor: top left-most point of the component
body: full set of holes that a component physically “covers” from a top-down perspective
pins: self-explanatory
nets: names for the nodes of the circuit

'''
def column_to_x(col_f,pitch=2.54):
    return col_f * pitch

def row_to_y(row, pitch=2.54):
    return row * pitch

def convertCenterToNominal(centers):
    nominals = {}
    for name, part in centers.items():
        for center in part:
            nominals[name] = (column_to_x(center[0]),row_to_y(center[1]))
    return nominals

def convertCornersToCenter(corners):
    # input: pins of the component
    # output: center of the component (for GCODE placement)
    avg_x = sum(p[0] for p in corners) / len(corners)
    avg_y = sum(p[1] for p in corners) / len(corners)
    return avg_x, avg_y

def extractComponentPlacements(text):
    #use regex to find all patterns of: letter number {}
    pattern = r"(\w+)\s*\{([^}]*)\}"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    converted = {}
    for name, body in matches:
        dict_body = ast.literal_eval("{" + body + "}")
        converted.setdefault(name, []).append(convertCornersToCenter(dict_body['pins']))
    print(converted)
    return converted

def extractWirePlacements(text):
    # Regex to capture the hole list contents
    wireText = text.split('wires')[1]
    pattern = r"'holes':\s*(\[[^\]]*\])"
    matches = re.findall(pattern, wireText)
    converted = {}
    for idx, body in enumerate(matches):
        body_lst = ast.literal_eval(body)
        xs = [p[0] for p in body_lst]
        ys = [p[1] for p in body_lst]
        if len(set(xs)) > 1:
            varying = xs
        else:
            varying = ys
        wireLength = max(varying) - min(varying) + 1
        name = f'W{wireLength}'
        converted.setdefault(name, []).append(convertCornersToCenter(body_lst))
    print(converted)
    return converted

def sendMoveCommand(board, body):
    #convert nominal board coordinate to nominal bed coordinate and send GCODE move cmd
    global GCODE
    X,Y = body
    o = [0,0,25]
    if board == 'placement':
        o[0] += X_ORIGIN_PLACEMENT + X
        o[1] = Y_ORIGIN_PLACEMENT - Y
    if board == 'pickup':
        o[0] += X_ORIGIN_PICKUP + X
        o[1] = Y_ORIGIN_PICKUP - Y
    gcode_command = f"""
    G90 
    G0 F6000 X{round(o[0],3)} Y{round(o[1],3)} 
    G0 F6000 Z25
                    """
    GCODE += gcode_command
    payload = {
        "script": gcode_command
    }
    # Send POST request
    response = requests.post(MOONRAKER_URL, json=payload)
    # Check response
    if response.status_code == 200:
        pass
    else:
        print(f"Move Error: {response.status_code}: {response.text}")

def passiveZ():
    global GCODE
    gcode_command = f"""
        G0 Z{PASSIVE_HEIGHT}
        """
    GCODE += gcode_command
    payload = {
        "script": gcode_command
    }
    # Send POST request
    response = requests.post(MOONRAKER_URL, json=payload)
    # Check response
    if response.status_code == 200:
        # print(f"Raised Z to passive height")
        pass
    else:
        print(f"Error {response.status_code}: {response.text}")

def actuateDropper(board):
    #if board is placement, lower z axis, release pump, raise
    global GCODE
    if board == 'placement':
        gcode_command = f"""
        G0 Z{PLACE_HEIGHT}
        VACUUM_OFF
        G0 Z{PASSIVE_HEIGHT}
        """
    elif board == 'pickup':
        gcode_command = f"""
        G0 Z{PICKUP_HEIGHT}
        VACUUM_ON
        G0 Z{PASSIVE_HEIGHT}
        """
    else:
        print('invalid board name')
        return -1
    GCODE += gcode_command
    payload = {
        "script": gcode_command
    }
    # Send POST request
    response = requests.post(MOONRAKER_URL, json=payload)
    # Check response
    if response.status_code == 200:
        #print(f"Successfully actuated dropper")
        pass
    else:
        print(f"Error {response.status_code}: {response.text}")

def place(body):
    X, Y = body
    sendMoveCommand('placement', (X, Y))
    actuateDropper('placement')
    return (X,Y)

def pickupComponent(id):
    name_pattern = r"^([A-Z]+)[0-9]+$"
    num_pattern = r"^[A-Z]+([0-9]+)$"
    try: #if part follows format {name}{num}, the following will succeed
        part_type = re.findall(name_pattern, id, flags=re.DOTALL)[0]
        part_num = int(re.findall(num_pattern, id, flags=re.DOTALL)[0])
    except: #if not, assume that it's just {name} and set num to 1
        part_type = id
        part_num = 1
    #pins_dummy = [(col_dict[part_type],(part_num-1)*len_dict[part_type]),(col_dict[part_type],(part_num)*len_dict[part_type])]
    center_X, center_Y = convertCornersToCenter([(col_dict[part_type],(part_num-1)*(len_dict[part_type]-1)),
                                                  (col_dict[part_type],(part_num)*(len_dict[part_type]-1))])
    #note that above line doesn't account for leaving 1 hole empty after each component in a column
    nominalsDict = convertCenterToNominal({"dummy": [(center_X, center_Y)]})
    nominal_X, nominal_Y = nominalsDict['dummy']
    sendMoveCommand('pickup', (nominal_X, nominal_Y))
    actuateDropper('pickup')
    return [(center_X, center_Y),(nominal_X, nominal_Y)]

def pickupWire(id):
    center_X, center_Y = convertCornersToCenter([(col_dict[id], (wires_used[id]) * (len_dict[id] - 1)),
                                                 (col_dict[id], (wires_used[id]+1) * (len_dict[id] - 1))])
    # note that above line doesn't account for leaving 1 hole empty after each component in a column
    nominalsDict = convertCenterToNominal({"dummy": [(center_X, center_Y)]})
    nominal_X, nominal_Y = nominalsDict['dummy']
    sendMoveCommand('pickup', (nominal_X, nominal_Y))
    actuateDropper('pickup')
    return [(center_X, center_Y), (nominal_X, nominal_Y)]


def run_input(input):
    centerComponentList = extractComponentPlacements(input)
    centerWireList = extractWirePlacements(input)
    componentNominals = convertCenterToNominal(centerComponentList)
    wireNominals = convertCenterToNominal(centerWireList)
    print('Nominal Board Component Placements: ', componentNominals, '\nNominal Board Wire Placements: ', wireNominals)
    passiveZ()
    for name, body in componentNominals.items():
        board, nom = pickupComponent(name)
        print(f'Picked up {name} at grid {board} nominal {nom}')
        place(body)
        print(f'Placed {name} at grid {centerComponentList[name]} nominal {body}')
        time.sleep(1)
    for name, body in wireNominals.items():
        board,nom = pickupWire(name)
        print(f'Picked up {name} at grid {[board]} nominal {nom}')
        grid = place(body)
        time.sleep(1)
        print(f'Placed {name} at grid {grid[0], grid[1]} nominal {body}')
    with open("gcode.txt", "w") as f:
        f.write(GCODE)



if __name__ == "__main__":
    input = """
    components:
    R1 {'anchor': (0, 0), 'body': [(0, 0), (0, 0), (0, 2), (0, 3), (0, 4), (0, 5)], 'pins': [(0, 0), (0, 5)], 'nets': ('V+', 'N1')}
    C1 {'anchor': (2, 0), 'body': [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5)], 'pins': [(2, 0), (2, 5)], 'nets': ('N1', 'N2')}
    L1 {'anchor': (4, 0), 'body': [(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 5)], 'pins': [(4, 0), (4, 5)], 'nets': ('N2', 'N3')}
    LED {'anchor': (7, 0), 'body': [(7, 0), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5)], 'pins': [(7, 0), (7, 5)], 'nets': ('N3', 'GND')}
    
    wires:
    {'net': 'WIRE', 'holes': [(9, 0), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5)]}


    """
    #extractWirePlacements(input)
    #extractComponentPlacements(input)
    run_input(input)