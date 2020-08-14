#!/usr/bin/env python

'''
client functionality
'''


from time import sleep  # pylint: disable=unused-import
import struct  # pylint: disable=unused-import
import sys
import threading
import socket
import ao  # pylint: disable=import-error
import mad  # pylint: disable=import-error


# globals
BOOL_PLAY = False
MESSAGE_LENGTH = 4123
END_OF_LINE = '|>^,^<|'
END_OF_MESSAGE = '|>^,^<|>^,^<'
URL = '127.0.0.1'


# pylint: disable=too-few-public-methods, useless-object-inheritance, invalid-name
class mywrapper(object):
    '''
    Wrapper object for reading audio data to trick Mad audio library
    '''

    def __init__(self):
        '''
        initialize mywrapper()
        '''
        self.mf = None # pylint: disable=invalid-name
        self.data = ""

    def read(self, size):
        '''
        read a specific size by returning that many bytes
        and updating our remaining data
        '''
        result = self.data[:size]
        self.data = self.data[size:]
        return result


def list_songs(data):
    '''
    return the list of songs parsed from the data received from server
    '''
    song_list = data.split(END_OF_LINE)  # split by EOL character '>^,^<'

    for song in song_list:
        if song[0].isdigit():  # if first character is song ID, print
            print(song)


def create_message(msg_type, song_id=None):
    '''
    create play message to be sent to server
    '''
    if msg_type == 'play':
        return 'PLAY|{}/{}|>^,^<|>^,^<'.format(URL, song_id)
    if msg_type == 'list':
        return 'LIST|{}|>^,^<|>^,^<'.format(URL)
    if msg_type == 'stop':
        return 'STOP|{}|>^,^<|>^,^<'.format(URL)
    if msg_type == 'setup':
        return 'SETUP|{}|>^,^<|>^,^<'.format(URL)
    if msg_type == 'teardown':
        return 'TEARDOWN|{}|>^,^<|>^,^<'.format(URL)
    return None


def send_request(msg_type, sock, message=None):
    '''
    request sender helper
    '''

    # if the message type is play, check message for song_id,
    # create message, and send
    if msg_type == 'play':
        try:
            song_id = message.split(' ')[1]
            sock.sendall(create_message(msg_type, song_id))
        except ValueError:
            print("Invalid argument")
    elif msg_type == 'stop':
        sock.sendall(create_message(msg_type))
    # create message, if type exists, send
    else:
        message = create_message(msg_type)
        if message:
            sock.sendall(message)


def stop(wrap, cond_filled):
    '''
    stop helper function
    '''
    # use lock to reset data in wrapper object
    cond_filled.acquire()
    wrap.data = ""
    cond_filled.release()


def recv_helper(data_length, sock, end):
    '''
    helper function to receive data
    '''
    # set up empty data + length
    data = ""
    length = 0
    end_len = len(end)

    # receive data in recv_data, add to data, break when we
    # receive the correct end message code, '>^,^<>^,^<'
    while len(data) < data_length:

        # receive data
        recv_data = sock.recv(data_length - len(data))

        # # add length of received data to length
        # length += len(recv_data)

        # add received data to data buff
        data += recv_data

        # check for end to break out of loop
        if data[-end_len:] == end:
            return data


def recv_thread_func(wrap, cond_filled, sock):
    '''
    Receive messages.  If they're responses to info/list, print
    the results for the user to see.  If they contain song data, the
    data needs to be added to the wrapper object.  Be sure to protect
    the wrapper with synchronization, since the other thread is using
    it too!
    '''
    while True:
        # get full message
        message_data = recv_helper(MESSAGE_LENGTH, sock, END_OF_MESSAGE)

        # read data to check what the message from server says

        if message_data is not None:
            data_tokens = message_data.split('|')

            if 'MEOW' in message_data:
                if '300' in message_data: # list
                    list_songs(message_data)
                elif '100' in message_data: # audio
                    audio_data = data_tokens[3: len(data_tokens) - 2]
                    audio_data = "|".join(audio_data)
                    cond_filled.acquire()
                    if BOOL_PLAY == True:
                        wrap.data += audio_data
                    cond_filled.release()

                # code for OK, used for setup, teardown, stop ACKs
                elif '200' in message_data:
                    continue
            elif 'HISS' in message_data:
                print("error")

            cond_filled.acquire()

            if wrap.mf is None:
                wrap.mf = mad.MadFile(wrap)

            cond_filled.release()


def play_thread_func(wrap, cond_filled, dev):
    '''
    If there is song data stored in the wrapper object, play it!
    Otherwise, wait until there is.  Be sure to protect your accesses
    to the wrapper with synchronization, since the other thread is
    using it too!
    '''

    while True:
        if wrap.mf is not None:
            cond_filled.acquire()
            buf = wrap.mf.read()
            cond_filled.release()
            
            if buf is not None and BOOL_PLAY == True:
                dev.play(buffer(buf), len(buf)) #pylint: disable=undefined-variable


def main():
    '''
    main function
    '''

    if len(sys.argv) < 3:
        print('Usage: {} <server name/ip> <server port>'.format(sys.argv[0]))
        sys.exit(1)

    # Create a pseudo-file wrapper.
    wrap = mywrapper()

    global BOOL_PLAY #pylint: disable=global-statement

    # Create a condition variable to synchronize the receiver and
    # player threads. This implicitly creates a mutex lock too.
    cond_filled = threading.Condition()

    # Create a TCP socket and try connecting to the server.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((sys.argv[1], int(sys.argv[2])))

    # Create a thread whose job is to receive messages from the server,
    # using the socket, condition variable, and psuedo-file wrapper.
    recv_thread = threading.Thread(
        target=recv_thread_func,
        args=(wrap, cond_filled, sock)
    )

    recv_thread.daemon = True
    recv_thread.start()

    # set up audio device
    dev = ao.AudioDevice('pulse')

    # set up play thread
    play_thread = threading.Thread(
        target=play_thread_func,
        args=(wrap, cond_filled, dev)
    )

    # start play thread
    play_thread.daemon = True
    play_thread.start()

    # Enter our never-ending user I/O loop.
    # Because we imported the readline module above, raw_input gives us
    # nice shell-like behavior (up-arrow to go backwards, etc.).
    while True:
        line = raw_input('>> ') #pylint: disable=undefined-variable

        if ' ' in line:
            cmd, args = line.split(' ', 1)
        else:
            cmd = line

        if cmd in ['l', 'list']:
            print('The user asked for a list of all songs available.')

            # send request to server to list all available songs
            send_request('list', sock)

        elif cmd in ['p', 'play']:
            if ' ' not in line:
                print("Please type in a song ID to play")
                continue
            print('The user asked to play:', args)

            BOOL_PLAY = False
            # if already playing, stop and clear buffer
            send_request('stop', sock)
            stop(wrap, cond_filled)
            sleep(2)
            BOOL_PLAY = True
            # send request to server to play
            send_request('play', sock, line)

        elif cmd in ['s', 'stop']:
            print('The user asked to stop.')
            BOOL_PLAY = False

            # send request to server to stop sending packets
            send_request('stop', sock)

            # clear wrapper
            stop(wrap, cond_filled)

        elif cmd in ['quit', 'q', 'exit']:
            print('The user asked to exit.')
            sys.exit(0)

        else:
            print('Incorrect usage; please try again.')



if __name__ == '__main__':
    main()
