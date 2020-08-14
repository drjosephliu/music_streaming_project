'''
server.py
CIS 553, Project 6
Joe Liu, Adi Manjunath
joeliu, adithyam
'''
import os
import socket
import sys
from threading import Lock, Thread
from signal import signal, SIGPIPE, SIG_IGN
import errno

QUEUE_LENGTH = 10
SEND_BUFFER = 4096

# globals
END_OF_LINE = '|>^,^<|'
END_OF_MESSAGE = '>^,^<'
URL = '127.0.0.1/'


class Client: #pylint: disable=too-few-public-methods, too-many-instance-attributes
    '''
    per client struct
    '''
    def __init__(self, song_list, song_dir, conn, addr):
        '''
        Set up Client object variables
        '''
        self.lock = Lock()
        self.conn = conn
        self.addr = addr
        self.msg_list = []
        self.song_list = song_list
        self.song_dir = song_dir
        self.song_name = None


def client_write(client):
    '''
    Thread that sends music and lists to the client
    '''
    while True:
        while client.msg_list:
            client.lock.acquire()
            command = client.msg_list.pop(0)
            client.lock.release()

            if command == "list":
                data_string = create_message('list')
                for index, song in enumerate(client.song_list):
                    data_string += "{}. {}{}".format(index + 1, song, END_OF_LINE)
                data_string += END_OF_MESSAGE
                try:
                    client.conn.sendall(data_string)
                except client.conn.error, e:
                    if e.errno == errno.EPIPE:
                        print("Client has disconnected")
                    else:
                        print("Error: {}".format(e))
                        # return



            elif command == "play":
                print("CLIENT REQUESTED : {}".format(client.song_name))
                if client.song_name not in client.song_list:
                    data_string = create_message("hiss")

                    try:
                        client.conn.sendall(data_string)
                    except client.conn.error, e:
                        if e.errno == errno.EPIPE:
                            print("Client has disconnected")
                        else:
                            print("Error: {}".format(e))
                            return
                else:
                    with open(client.song_dir + client.song_name, "r") as song_file:
                        data = song_file.read(SEND_BUFFER)
                        print("SENDING: {}".format(client.song_name))
                        while data != "":
                            header = create_message("play")
                            data_string = header + data + END_OF_LINE + END_OF_MESSAGE
                            
                            try:
                                client.conn.sendall(data_string)
                            except client.conn.error, e:
                                if e.errno == errno.EPIPE:
                                    print("Client has disconnected")
                                else:
                                    print("Error: {}".format(e))
                                    # return
                            data = song_file.read(SEND_BUFFER)

            elif command == "stop":
                data_string = create_message("stop")
                
                try:
                    client.conn.sendall(data_string)
                except client.conn.error, e:
                    if e.errno == errno.EPIPE:
                        print("Client has disconnected")
                    else:
                        print("Error: {}".format(e))
                        # return

def client_read(client):
    '''
    read messages from client
    '''
    received_data = client.conn.recv(SEND_BUFFER)
    temp_data = received_data

    # while there is still data to be received
    while received_data:
        client.lock.acquire()
        if 'LIST' in temp_data:
            client.msg_list.append("list")
        elif 'PLAY' in temp_data:
            client.msg_list.append("play")
            if temp_data.split("|")[1][-1].isdigit():
                i = int(temp_data.split("|")[1][-1])
                if i <= len(client.song_list):
                    client.song_name = client.song_list[i-1]
        elif 'STOP' in temp_data:
            client.msg_list.append("stop")
        client.lock.release()
        temp_data = ""
        received_data = client.conn.recv(SEND_BUFFER)
        temp_data += received_data

def create_message(msg_type): #pylint: disable=too-many-return-statements
    '''
    create message function helper to send to client
    '''
    if msg_type == 'play':
        return "MEOW|100{}".format(END_OF_LINE)
    if msg_type == 'setup':
        return "MEOW|200{}{}".format(END_OF_LINE, END_OF_MESSAGE)
    if msg_type == 'teardown':
        return "MEOW|200{}{}".format(END_OF_LINE, END_OF_MESSAGE)
    if msg_type == "list":
        return "MEOW|300{}".format(END_OF_LINE)
    if msg_type == "stop":
        return "MEOW|200{}{}".format(END_OF_LINE, END_OF_MESSAGE)
    if msg_type == "hiss":
        return "HISS|404{}{}".format(END_OF_LINE, END_OF_MESSAGE)
    return None

def get_mp3s(musicdir):
    '''
    get mp3s in directory helper function
    '''
    songs = []
    for filename in os.listdir(musicdir):
        if not filename.endswith(".mp3"):
            continue
        songs.append(filename)
    return songs

def server_setup(server_port):
    '''
    server setup helper function
    '''
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFFER)
    server_socket.bind(('127.0.0.1', server_port))
    server_socket.listen(QUEUE_LENGTH)
    return server_socket


def main():
    '''
    main() function
    '''

    if len(sys.argv) != 3:
        sys.exit("Usage: python server.py [port] [musicdir]")
    if not os.path.isdir(sys.argv[2]):
        sys.exit("Directory '{0}' does not exist".format(sys.argv[2]))

    port = int(sys.argv[1])
    music_dir = sys.argv[2]
    if not music_dir.endswith("/"):
        music_dir = music_dir + "/"

    song_list = get_mp3s(music_dir)

    threads = []

    server_socket = server_setup(port)

    while True:
        conn, addr = server_socket.accept()
        client = Client(song_list, music_dir, conn, addr)
        t = Thread(target=client_read, args=(client,)) #pylint: disable=invalid-name
        threads.append(t)
        t.start()
        t = Thread(target=client_write, args=(client,)) #pylint: disable=invalid-name
        threads.append(t)
        t.start()

    server_socket.close()


if __name__ == "__main__":
    main()
