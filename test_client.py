# Echo client program
import socket

HOST = '127.0.0.1'    # The remote host
PORT = 50007              # The same port as used by the server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))


while True:

	line = raw_input(">>")

	s.sendall(line)
	data = s.recv(1024)
	print 'Received', repr(data)
	