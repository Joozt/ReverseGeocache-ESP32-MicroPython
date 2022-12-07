from time import sleep, time
from math import radians, cos, sin, atan2, sqrt
from machine import Pin, SoftI2C, PWM, UART
from ssd1306 import SSD1306_I2C
from rtttl import RTTTL

# Coordinates can be copied from Google Maps (use sattelite view for better results)
FIRST_DESTINATION_LAT = 52.37823186700114
FIRST_DESTINATION_LON = 4.899774671697002
SECOND_DESTINATION_LAT = 51.92339875478843
SECOND_DESTINATION_LON = 4.470300454531137
MAX_NUMBER_OF_ATTEMPTS = 50
MAX_DISTANCE_KM_TO_DESTINATIONS = 0.02
SECONDS_UNTIL_SHOWING_NO_GPS_MESSAGE = 30
SECONDS_UNTIL_SHOWING_BE_PATIENT_MESSAGE = 60
SECONDS_UNTIL_TURNING_OFF_AFTER_GPS_FOUND = 60
SECONDS_UNTIL_TURNING_OFF_WHEN_NO_GPS_FOUND = 300

class State:
    INIT = 0
    WELCOME = 1
    NO_ATTEMPTS_REMAINING = 2
    SEARCHING_GPS = 3
    GPS_FIX_FOUND = 4
    NO_GPS_FIX_FOUND = 5
    BE_PATIENT = 6
    NOT_CLOSEBY = 7
    SINGLE_COMPLETED = 8
    ALL_COMPLETED = 9
    GREETINGS = 10

class LocationCompleted:
    NONE = 0
    FIRST = 1
    SECOND = 2

state = State.INIT
location_completed = LocationCompleted.NONE
destination_lat = FIRST_DESTINATION_LAT
destination_lon = FIRST_DESTINATION_LON
attempt_count = 0
progress_bar_value = 0
distance_km = -1
latitude = 0.0
longitude = 0.0
gps_time = ''
no_gps_message_time = time() + SECONDS_UNTIL_SHOWING_NO_GPS_MESSAGE
be_patient_message_time = time() + SECONDS_UNTIL_SHOWING_BE_PATIENT_MESSAGE
be_patient_message_end_time = time() + SECONDS_UNTIL_SHOWING_BE_PATIENT_MESSAGE + SECONDS_UNTIL_SHOWING_NO_GPS_MESSAGE
distance_showing_time = 0
attempt_time = time() + SECONDS_UNTIL_TURNING_OFF_WHEN_NO_GPS_FOUND

gps_module = UART(2, baudrate=9600, timeout=1000)
display = SSD1306_I2C(width=128, height=32, i2c=SoftI2C(scl=Pin(22), sda=Pin(21)))
buzzer = PWM(Pin(19), duty=0)
servo_lock = PWM(Pin(23), freq=50, duty=60) # Initiate in closed state
power_control = Pin(4, Pin.OUT, Pin.PULL_DOWN)

def play_tune(tune):
    rtttl = RTTTL(tune)
    for freq, msec in rtttl.notes():
        if freq > 0:
            buzzer.freq(int(freq))
            buzzer.duty(512)
        sleep(msec*0.0006)
        buzzer.duty(0)
        sleep(0.025)

def play_start_tune():
    play_tune('Mission Impossible:d=16,o=6,b=95:32d,32d#,32d,32d#,32d,32d#,32d,32d#,32d,32d,32d#,32e,32f,32f#,32g,g,8p,g,8p,a#,p,c7,p,g,8p,g,8p,f,p,f#,p,g,8p,g,8p,a#,p,c7,p,g,8p,g,8p')

def play_winning_tune():
    play_tune('A-Team:d=8,o=5,b=125:4d#6,a#,2d#6,16p,g#,4a#,4d#.,p,16g,16a#,d#6,a#,f6,2d#6,16p,c#.6,16c6,16a#,g#.,2a#')

def play_losing_tune():
    play_tune('Lost:d=8,o=5,b=300:d#,c#,c,1a#4')

def show_welcome():
    display.fill(0)
    display.text('Welcome!', 0, 0)
    display.text('Good luck with', 0, 10)
    display.text('the puzzle!', 0, 20)
    display.show()

def show_attempt():
    display.fill(0)
    display.text('Attempt {} of {}'.format(attempt_count, MAX_NUMBER_OF_ATTEMPTS), 0, 0)
    display.show()

def show_distance():
    display.fill(0)
    display.text("Distance:{:.2f}km".format(distance_km), 0, 0)
    show_progress_bar()
    display.show()

def update_progress_bar():
    global progress_bar_value
    if progress_bar_value == 128:
        progress_bar_value = 0
    show_progress_bar()
    display.show()
    progress_bar_value += 1

def show_progress_bar():
    for x in range(128):
        display.pixel(x, 31, x < progress_bar_value)

def show_no_gps():
    display.fill(0)
    display.text('No GPS signal', 0, 0)
    display.text('found.', 0, 10)
    show_progress_bar()
    display.show()

def show_be_patient():
    display.fill(0)
    display.text('Even outside it', 0, 0)
    display.text('can take a', 0, 10)
    display.text('couple of mins', 0, 20)
    show_progress_bar()
    display.show()

def show_failed():
    display.text('SORRY :-(', 0, 10)
    display.show()

def show_single_completed():
    display.fill(0)
    display.text("Distance:{:.2f}km".format(distance_km), 0, 0)
    display.text('Well done! On', 0, 10)
    display.text('with the next...', 0, 20)
    display.show()

def show_all_completed():
    display.fill(0)
    if distance_km >= 0.0:
        display.text("Distance:{:.2f}km".format(distance_km), 0, 0)
    display.text('CONGRATULATIONS!', 0, 15)
    display.show()

def show_greetings():
    display.fill(0)
    display.text("Greetings", 0, 0)
    display.text("from", 0, 10)
    display.text("Joozt", 0, 20)
    display.show()

def read_attempt_counter():
    global attempt_count
    file = open('counter.txt')
    attempt_count = int(file.read())
    print("Count: {}".format(attempt_count))
    file.close()

def increment_attempt_counter():
    global attempt_count
    attempt_count += 1
    file = open('counter.txt', 'w')
    file.write(str(attempt_count))
    file.close()

def write_current_location():
    file = open('locations.txt', 'a')
    file.write("{} https://maps.google.com/?q={},{}\n".format(gps_time, latitude, longitude))
    file.close()

def servo_lock_open():
    servo_lock.duty(100)

def read_location_completed():
    global location_completed
    file = open('completed.txt')
    location_completed = int(file.read())
    print("Completed: {}".format(location_completed))
    file.close()
    update_destination()

def increment_location_completed():
    global location_completed
    location_completed += 1
    file = open('completed.txt', 'w')
    file.write(str(location_completed))
    file.close()
    update_destination()

def update_destination():
    global destination_lat, destination_lon
    if location_completed == LocationCompleted.NONE:
        destination_lat = FIRST_DESTINATION_LAT
        destination_lon = FIRST_DESTINATION_LON
    if location_completed == LocationCompleted.FIRST:
        destination_lat = SECOND_DESTINATION_LAT
        destination_lon = SECOND_DESTINATION_LON

def turn_off():
    power_control.on()
    # display.poweroff()
    # while True:
    #     sleep(1)

def get_distance_km():
    global distance_km, latitude, longitude, gps_time
    line = str(gps_module.readline())
    parts = line.split(',')
    if (len(parts) == 15 and parts[0] == "b'$GPGGA"):
        if(parts[1] and parts[2] and parts[3] and parts[4] and parts[5] and parts[6] and parts[7]):
            print(line)
            latitude = convert_to_degrees(parts[2])
            if parts[3] == 'S':
                latitude = -float(latitude)
            longitude = convert_to_degrees(parts[4])
            if parts[5] == 'W':
                longitude = -float(longitude)
            satellites = int(parts[7])
            distance_km = calculate_distance_km(destination_lat, destination_lon, latitude, longitude)
            gps_time = parts[1][0:2] + ":" + parts[1][2:4] + ":" + parts[1][4:6]
            print("----------------------")
            print("Latitude: {}".format(latitude))
            print("Longitude: {}".format(longitude))
            print("Satellites: {}".format(satellites))
            print("Distance: {:.2f}km".format(distance_km))
            print("Time: {}".format(gps_time))
            print("----------------------")

def convert_to_degrees(rawDegrees):
    rawAsFloat = float(rawDegrees)
    firstDigits = int(rawAsFloat/100)
    nextTwoDigits = rawAsFloat - float(firstDigits*100)
    converted = float(firstDigits + nextTwoDigits/60.0)
    converted = '{0:.6f}'.format(converted)
    return float(converted)

def calculate_distance_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi       = radians(lat2 - lat1)
    dlambda    = radians(lon2 - lon1)
    a = sin(dphi/2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda/2) ** 2
    return 2 * 6372.8 * atan2(sqrt(a), sqrt(1 - a))


def game_loop():
    global state, distance_km, distance_showing_time

    if state == State.INIT:
        read_location_completed()
        if location_completed >= LocationCompleted.SECOND:
            state = State.ALL_COMPLETED
        else:
            read_attempt_counter()
            increment_attempt_counter()
            if attempt_count > MAX_NUMBER_OF_ATTEMPTS:
                state = State.NO_ATTEMPTS_REMAINING
            else:
                state = State.WELCOME

    if state == State.NO_ATTEMPTS_REMAINING:
        show_attempt()
        show_failed()
        play_losing_tune()
        sleep(10)
        state = State.SEARCHING_GPS # Continue anyway

    if state == State.WELCOME:
        show_welcome()
        play_start_tune()
        show_attempt()
        sleep(4)
        state = State.SEARCHING_GPS

    if state == State.SEARCHING_GPS:
        get_distance_km()
        update_progress_bar()
        if distance_km >= 0.0:
            state = State.GPS_FIX_FOUND
        else:
            if time() > be_patient_message_time and time() < be_patient_message_end_time and attempt_count >= 2 and attempt_count <= 7:
                state = State.BE_PATIENT
            elif time() > no_gps_message_time:
                state = State.NO_GPS_FIX_FOUND

    if state == State.GPS_FIX_FOUND:
        if distance_showing_time == 0:
            write_current_location()
            distance_showing_time = time() + SECONDS_UNTIL_TURNING_OFF_AFTER_GPS_FOUND
        if time() > distance_showing_time:
            turn_off()

        show_distance()
        if distance_km < MAX_DISTANCE_KM_TO_DESTINATIONS:
            state = State.SINGLE_COMPLETED
        else:
            get_distance_km()
            update_progress_bar()

    if state == State.NO_GPS_FIX_FOUND:
        show_no_gps()
        state = State.SEARCHING_GPS

    if state == State.BE_PATIENT:
        show_be_patient()
        state = State.SEARCHING_GPS

    if state == State.SINGLE_COMPLETED:
        increment_location_completed()
        if location_completed >= LocationCompleted.SECOND:
            state = State.ALL_COMPLETED
        else:
            show_single_completed()
            play_start_tune()
            sleep(10)
            distance_km = -1
            state = State.SEARCHING_GPS

    if state == State.ALL_COMPLETED:
        servo_lock_open()
        show_all_completed()
        play_winning_tune()
        sleep(10)
        state = State.GREETINGS

    if state == State.GREETINGS:
        show_greetings()
        sleep(60)
        turn_off()

    if time() > attempt_time:
        turn_off()


while True:
    game_loop()
