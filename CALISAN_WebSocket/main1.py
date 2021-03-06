# Author: Eduard Cuba
# Email: xcubae00@stud.fit.vutbr.cz
# original
# Last modified: 26.12.2017
# Desc: Simple HTTP server for ESP8266 LED control


import machine
import network
import socket
import os
import select

# set up AP
#ap_if = network.WLAN(network.AP_IF)
#ap_if.config(essid="YARINLAR", authmode=network.AUTH_WPA_WPA2_PSK, password="akmanakman")

ap_if = network.WLAN(network.STA_IF)
print('connecting to network...')
ap_if.active(True)
ap_if.connect("YARINLAR", "akmanakman")
while not ap_if.isconnected():
    pass
print('configuration:', ap_if.ifconfig())
print('Server is running...')



# set up server socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)

# prepare page template
with open("index.html") as f:
    html = f.read()
    systemData = os.uname()
    systemInfo = """
    {}
    <ul>
        <li>System: {}</li>
        <li>Release: {}</li>
        <li>MicroPython: {}</li>
    </ul>
    """.format(systemData[4], systemData[0], systemData[2], systemData[3])
    html = html.replace("$SYSTEM_INFO", systemInfo, 1)
    f.close()

# prepare pins
p2 = machine.Pin(2, machine.Pin.OUT, value=1)
p4 = machine.Pin(4, machine.Pin.OUT, value=0)
p16 = machine.Pin(16, machine.Pin.OUT, value=1)

class ConfigHolder:
    """ Configuration holder object """
    p2e = False
    p4e = False
    p16e = False
    blink = False
    rotate = False
    rotateState = 0
config = ConfigHolder()


def handleAsset(what, client):
    """ Handle asset file (*.css, *.ico) """
    try:
        with open(what) as f:
            while True:
                chunk = f.read(256)
                if chunk:
                    client.write(chunk)
                else:
                    break
            f.close()
    except Exception as e:
        print(e)


def resetLEDs():
    config.p2e = True
    config.p4e = True
    config.p16e = True
    p2.off()
    p4.on()
    p16.off()


def handleGET(what, rest, client):
    """ Respond to GET request """
    # read the message
    while True:
        line = rest.readline()
        if not line or line == b'\r\n':
            break
    # get requested attribute
    what = what[1:].decode("utf-8")
    # LED toogle request
    if what.startswith("TOOGLE_LED2"):
        config.p2e = not config.p2e
    elif what.startswith("TOOGLE_LED4"):
        config.p4e = not config.p4e
    elif what.startswith("TOOGLE_LED16"):
        config.p16e = not config.p16e
    elif what.startswith("BLINK"):
        # sequence request
        config.blink = not config.blink
        if config.blink:
            config.rotate = False
            resetLEDs()
    elif what.startswith("ROTATE"):
        # rotation request
        config.rotate = not config.rotate
        if config.rotate:
            config.blink = False
            resetLEDs()
    elif what.endswith("css") or what.endswith("ico"):
        # asset request
        return handleAsset(what, client)

    # fill the response template
    res = html.replace("$LED2_STATUS", "ON" if config.p2e else "OFF", 1)
    res = res.replace("$LED4_STATUS", "ON" if config.p4e else "OFF", 1)
    res = res.replace("$LED16_STATUS", "ON" if config.p16e else "OFF", 1)
    res = res.replace("$BLINK_STATUS", "ON" if config.blink else "OFF", 1)
    res = res.replace("$ROTATE_STATUS", "ON" if config.rotate else "OFF", 1)
    client.write(res)


def refresh():
    """ Set pin voltages according to configuration """
    if config.blink:
        # blinking enabled - change values of enabled pins
        if config.p2e:
            p2.value(not p2.value())
        else:
            p2.value(True)
        if config.p4e:
            p4.value(not p4.value())
        else:
            p4.value(False)
        if config.p16e:
            p16.value(not p16.value())
        else:
            p16.value(True)
    elif config.rotate:
        # rotation
        config.rotateState = (config.rotateState + 1) % 3
        p2.value(not (config.rotateState == 0 and config.p2e))
        p4.value(config.rotateState == 1 and config.p4e)
        p16.value(not (config.rotateState == 2 and config.p16e))
    else:
        # blinking disabled - set pins to static values
        p2.value(not config.p2e)
        p4.value(config.p4e)
        p16.value(not config.p16e)


# main server loop
while True:
    # loop for waiting for connection and blinking
    while True:
        ready, _, _ = select.select([s], [], [], 0.5)
        if ready:
            # accept new request
            cl, addr = s.accept()
            break
        else:
            # timeout exceeded
            refresh()
    # process request
    data = cl.makefile('rwb', 0)
    # get HTTP header
    line = data.readline()
    tokens = line.split()
    if len(tokens) < 2:
        continue
    # respond to the request
    if tokens[0] == b'GET':
        handleGET(tokens[1], data, cl)
    cl.close()
