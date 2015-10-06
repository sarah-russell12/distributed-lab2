#!/usr/bin/env python3

# -----------------------------------------------------------------------------
# Distributed Systems (TDDD25)
# -----------------------------------------------------------------------------
# Author: Sergiu Rafiliu (sergiu.rafiliu@liu.se)
# Modified: 31 July 2013
#
# Copyright 2012 Linkoping University
# -----------------------------------------------------------------------------

"""Server that serves clients trying to work with the database."""

import threading
import socket
import json
import random
import argparse

import sys
sys.path.append("../modules")
from Server.database import Database
from Server.Lock.readWriteLock import ReadWriteLock

# -----------------------------------------------------------------------------
# Initialize and read the command line arguments
# -----------------------------------------------------------------------------

rand = random.Random()
rand.seed()
description = """\
Server for a fortune database. It allows clients to access the database in
parallel.\
"""
parser = argparse.ArgumentParser(description=description)
parser.add_argument(
    "-p", "--port", metavar="PORT", dest="port", type=int,
    default=rand.randint(1, 10000) + 40000, choices=range(40001, 50000),
    help="Set the port to listen to. Values in [40001, 50000]. "
         "The default value is chosen at random."
)
parser.add_argument(
    "-f", "--file", metavar="FILE", dest="file", default="dbs/fortune.db",
    help="Set the database file. Default: dbs/fortune.db."
)
opts = parser.parse_args()

db_file = opts.file
server_address = ("", opts.port)

# -----------------------------------------------------------------------------
# Auxiliary classes
# -----------------------------------------------------------------------------

class Server(object):

    """Class that provides synchronous access to the database."""

    def __init__(self, db_file):
        self.db = Database(db_file)
        self.rwlock = ReadWriteLock()

    # Public methods

    # These act as wrappers for processes in the underlying database
    def read(self):
        #print("Server trying to read")
        s=self.db.read();
        #print("Server has read fortune:"+s)
        return(s)

    def write(self, fortune):
        # We return the result of self.db.write even though this function has no return statement.
        # This provides extensibility, since future versions may return some information such as a status code.
        
        #print("trying to write fortune:" + fortune)
        self.db.write(fortune)
        #print("Server thinks it worked")
        return("Successfully wrote fortune \""+fortune+"\" to database")


class Request(threading.Thread):

    """ Class for handling incoming requests.
        Each request is handled in a separate thread.
    """

    def __init__(self, db_server, conn, addr):
        threading.Thread.__init__(self)
        self.db_server = db_server
        self.conn = conn
        self.addr = addr
        self.daemon = True

    # Private methods

    def process_request(self, request):
        """ Process a JSON formated request, send it to the database, and
            return the result.

            The request format is:
                {
                    "method": called_method_name,
                    "args": called_method_arguments
                }

            The returned result is a JSON of the following format:
                -- in case of no error:
                    {
                        "result": called_method_result
                    }
                -- in case of error:
                    {
                        "error": {
                            "name": error_class_name,
                            "args": error_arguments
                        }
                    }
        """
        
        output = dict()

        # Try to get requested method from this instance and execute with the given arguments.
        # If this fails, capture the exception and return that.
        try:
            # Throws a TypeError if input is not string
            # Throws a ValueError if input is not valid JSON
            requestObj = json.loads(request)
            
            # Throws an AttributeError if requested method not present
            method = getattr(self.db_server,requestObj["method"])

            # Throws a TypeError if argument types do not match method header
            result = method(*requestObj["args"])
            #print("Result of operation:"+result)
            output["result"] = result

        except Exception as e:
            #print(e)
            #print("test")
            output["error"] = dict()
            output["error"]["name"] = type(e).__name__
            output["error"]["args"] = args(e)
        
        finally:
            #print("Server executing finally condition")
            #print("State of output dict:")
            #print(output)
            s = json.dumps(output)
            #print("State of dumped output dict:")
            #print(s)
            return(s)
    
    def run(self):
        try:
            # Threat the socket as a file stream.
            worker = self.conn.makefile(mode="rw")
            # Read the request in a serialized form (JSON).
            request = worker.readline()
            # Process the request.
            result = self.process_request(request)

            #print("In run:"+result)
            # Send the result.
            worker.write(result + '\n')
            worker.flush()
        except Exception as e:
            # Catch all errors in order to prevent the object from crashing
            # due to bad connections coming from outside.
            print("The connection to the caller has died:")
            print("\t{}: {}".format(type(e), e))
        finally:
            self.conn.close()

# -----------------------------------------------------------------------------
# The main program
# -----------------------------------------------------------------------------

print("Listening to: {}:{}".format(socket.gethostname(), opts.port))
with open("srv_address.tmp", "w") as f:
    f.write("{}:{}\n".format(socket.gethostname(), opts.port))

sync_db = Server(db_file)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(server_address)
server.listen(1)

print("Press Ctrl-C to stop the server...")

try:
    while True:
        try:
            conn, addr = server.accept()
            req = Request(sync_db, conn, addr)
            print("Serving a request from {0}".format(addr))
            req.start()
        except socket.error:
            continue
except KeyboardInterrupt:
    pass
