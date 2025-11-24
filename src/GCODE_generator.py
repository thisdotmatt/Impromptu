import re
import ast
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
X_ORIGIN_PLACEMENT = 23.7
Y_ORIGIN_PLACEMENT = 228.25
X_ORIGIN_PICKUP = 156.7
Y_ORIGIN_PICKUP = 193.25
PLACE_HEIGHT = 14
PICKUP_HEIGHT = 15
PASSIVE_HEIGHT = 45

#pickup trackers, do not change these
col_dict = {'R': 0, 'C': 3, 'L': 6, 'LED': 9, 'W2': 8, 'W3': 10}
len_dict = {'R': 6, 'C': 6, 'L': 6, 'LED': 6, 'W2': 6, 'W3': 6}
wires_used = {'W2': 0, 'W3': 0}

#GCODE To dump
GCODE = ''

'''
input is:
components:
R1 {'anchor': (1, 10), 'body': [(1, 10), (2, 10), (3, 10)], 'pins': [(1, 10), (3, 10)], 'nets': ('V+', 'N1')}
C1 {'anchor': (3, 1), 'body': [(3, 1), (4, 1), (5, 1)], 'pins': [(3, 1), (5, 1)], 'nets': ('N1', 'N2')}
L1 {'anchor': (5, 0), 'body': [(5, 0), (6, 0), (7, 0), (8, 0), (9, 0)], 'pins': [(5, 0), (9, 0)], 'nets': ('N2',
'N3')}
LED {'anchor': (7, 1), 'body': [(7, 1), (8, 1), (9, 1), (10, 1)], 'pins': [(7, 1), (10, 1)], 'nets': ('N3',
'GND')}
wires:
{'net': 'N1', 'holes': [(3, 7), (3, 4)]}
{'net': 'N3', 'holes': [(7, 2), (8, 2), (9, 2)]}
{'net': 'V+', 'holes': [(1, 11), (1, 14)]}
{'net': 'GND', 'holes': [(10, 0), (10, -3)]}
TERMS:
anchor: top left-most point of the component
body: full set of holes that a component physically “covers” from a top-down perspective
pins: self-explanatory
nets: names for the nodes of the circuit
'''

def column_to_x(col_f,pitch=2.54):
    col = int(col_f)
    # Special long distances
    special_spans = {
        (-3, 0): 6.7,
        (11, 14): 6.7
    }
    # Compute x for col by summing movement from 0
    x = 0.0
    c0 = 0   # origin col
    step = 1 if col >= c0 else -1
    for c in range(c0, col, step):
        next_c = c + step
        # Check if (c, next_c) matches one of the special spans
        used_special = False
        for (a, b), dist in special_spans.items():
            if (c == a and next_c == b) or (c == b and next_c == a):
                x += step * (dist / abs(b - a))  # per-column increment in that span
                used_special = True
                break
        # Normal spacing
        if not used_special:
            x += step * pitch
    return x

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
        wireLength = max(varying) - min(varying)
        name = f'W{wireLength}'
        converted.setdefault(name, []).append(convertCornersToCenter(body_lst))
    print(converted)
    return converted

def sendMoveCommand(board, body):
    #convert nominal board coordinate to nominal bed coordinate and send GCODE move cmd
    X,Y = body
    o = [X,0,25]
    if board == 'placement':
        o[0] += X_ORIGIN_PLACEMENT
        o[1] = Y_ORIGIN_PLACEMENT - Y
    if board == 'pickup':
        o[0] += X_ORIGIN_PICKUP
        o[1] = Y_ORIGIN_PICKUP - Y
    gcode_command = f"""
                        G90 
                        G0 X{round(o[0],3)} Y{round(o[1],3)} Z25
                    """
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

def actuateDropper(board):
    #if board is placement, lower z axis, release pump, raise
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
    payload = {
        "script": gcode_command
    }
    # Send POST request
    response = requests.post(MOONRAKER_URL, json=payload)
    # Check response
    if response.status_code == 200:
        print(f"Successfully actuated dropper")
    else:
        print(f"Error {response.status_code}: {response.text}")

def place(body):
    X, Y = body
    sendMoveCommand('placement', (X, Y))
    actuateDropper('placement')

def pickupComponent(id):
    name_pattern = r"^([A-Z]+)[0-9]+$"
    num_pattern = r"^[A-Z]+([0-9]+)$"
    try: #if part follows format {name}{num}, the following will succeed
        part_type = re.findall(name_pattern, id, flags=re.DOTALL)[0]
        part_num = int(re.findall(num_pattern, id, flags=re.DOTALL)[0])
    except: #if not, assume that it's just {name} and set num to 1
        part_type = id
        part_num = 1
    nominal_X = column_to_x(col_dict[part_type])# + 0.5)
    nominal_Y = row_to_y(part_num*len_dict[part_type] - (len_dict[part_type] / 2))
    sendMoveCommand('pickup', (nominal_X, nominal_Y))
    actuateDropper('pickup')

def pickupWire(id):
    nominal_X = column_to_x(col_dict[id])
    nominal_Y = row_to_y(wires_used[id]*len_dict[id])
    wires_used[id] += 1
    sendMoveCommand('pickup', (nominal_X, nominal_Y))
    actuateDropper('pickup')

def run_input(input):
    centerComponentList = extractComponentPlacements(input)
    centerWireList = extractWirePlacements(input)
    componentNominals = convertCenterToNominal(centerComponentList)
    wireNominals = convertCenterToNominal(centerWireList)
    print('Nominal Board Component Placements: ', componentNominals, '\nNominal Board Wire Placements: ', wireNominals)
    for name, body in componentNominals.items():
        pickupComponent(name)
        place(body)
        print(f'Placed {name} at board {centerComponentList[name]} nominal {body}')
        time.sleep(1)
    for name, body in wireNominals.items():
        pickupWire(name)
        place(body)
        time.sleep(1)
        print(f'Placed {name} at {body}')



if __name__ == "__main__":
    input = """
    R1 {'anchor': (1, 10), 'body': [(1, 10), (2, 10), (3, 10)], 'pins': [(1, 10), (3, 10)], 'nets': ('V+', 'N1')}
    C1 {'anchor': (3, 1), 'body': [(3, 1), (4, 1), (5, 1)], 'pins': [(3, 1), (5, 1)], 'nets': ('N1', 'N2')}
    L1 {'anchor': (5, 0), 'body': [(5, 0), (6, 0), (7, 0), (8, 0), (9, 0)], 'pins': [(5, 0), (9, 0)], 'nets': ('N2',
    'N3')}
    LED {'anchor': (7, 1), 'body': [(7, 1), (8, 1), (9, 1), (10, 1)], 'pins': [(7, 1), (10, 1)], 'nets': ('N3',
    'GND')}
    wires:
    {'net': 'N1', 'holes': [(3, 7), (3, 4)]}
    {'net': 'N3', 'holes': [(7, 2), (8, 2), (9, 2)]}
    {'net': 'V+', 'holes': [(1, 11), (1, 14)]}
    {'net': 'GND', 'holes': [(10, 0), (10, -3)]}
    """
    #extractWirePlacements(input)
    #extractComponentPlacements(input)
    run_input(input)