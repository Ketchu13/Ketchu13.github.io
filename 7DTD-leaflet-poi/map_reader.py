 
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of 7dtd-prefabs.
#
# 7dtd-prefabs is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 7dtd-prefabs is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 7dtd-prefabs. If not, see <http://www.gnu.org/licenses/>.
# Source code hosted at https://github.com/nicolas-f/7dtd-prefabs
# @author Nicolas Fortin github@nettrader.fr https://github.com/nicolas-f
# @author Nicolas Grimaud ketchu13@hotmail.com

import struct
import itertools
import getopt
import sys
import os
import time
import sqlite3
import shutil
from kfp_addpoi_GUI import *
from kfp_addpoi_nogui import *
try:
    from PIL import Image, ImageOps
except ImportError:
    print "This program require:"
    print "Pillow https://pillow.readthedocs.org/en/latest/"
    raw_input()
    exit(-1)

class Advanced_MapReader(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.settings = {}
        self.settings['game_player_path'] = None
        self.settings['tile_path'] = "tiles"
        self.settings['tile_zoom'] = 8
        self.settings['store_history'] = False
        self.settings['telnet_server'] = ""
        self.settings['password'] = ""
        self.settings['http_server_port'] = ""
        self.settings['ignRqt'] = False
        self.settings['ignTrack'] = False
        self.settings['wLPath'] = ""
        self.settings['poiPath'] = ""
        self.settings['verbose'] = False
        self.settings['www'] = ""
        self.settings['GUI'] = False
        # parse configfile options
        try:
            f = open('./config.kfp', "r")
            for i in f:
                i = i.strip()
                if len(i) > 0:
                    s = i.split("=")
                    key = s[0].strip()
                    value = s[1].strip()
                    self.settings[key] = value
        except:
            print("ERROR: file ./config.kfp does not exist or is improperly formatted")

        # parse command line options
        try:
            for opt, value in getopt.getopt(sys.argv[1:], "g:t:z:n:s:h:p:i:x:w:k:v:c:b:f:")[0]:
                if opt == "-g":
                     self.settings['game_player_path'] = value
                elif opt == "-t":
                    self.settings['tile_path'] = value
                elif opt == "-z":
                    self.settings['tile_zoom'] = int(value)
                elif opt == "-n":
                    self.settings['store_history'] = True
                    print "Store all version of tiles, may take huge disk space"
                elif opt == "-s":
                    self.settings['telnet_server'] = value
                    self.settings['sIp'] = value.split(':')[0]
                    self.settings['sPort'] = value.split(':')[1]
                elif opt == "-h":
                    self.settings['http_server'] = int(value)
                elif opt == "-p":
                    self.settings['sPass'] = value
                elif opt == "-i":
                    self.settings['ignRqt'] = True
                elif opt == "-x":
                    self.settings['ignTrack'] = True
                elif opt == "-w":
                    self.settings['wLPath'] = value
                elif opt == "-k":
                    self.settings['poiPath'] = value
                elif opt == "-v":
                    self.settings['verbose'] = True
                elif opt == "-c":
                    self.settings['www'] = value
                elif opt == "-b":
                    self.settings['GUI'] = value
                elif opt == "-f":
                    self.settings['FTPInfos'] = value
        except getopt.error, msg:
            print str(msg)
            self.usage()
            raw_input()
            exit(-1)
        if self.settings['game_player_path'] is None:
            # Show gui to select tile folder
            try:
                import tkFileDialog
                from Tkinter import Tk
                root = Tk()
                root.withdraw()
                opts = {"initialdir": os.path.expanduser("~\\AppData\\Roaming\\7DaysToDie\\Saves\\Random Gen\\"),
                        "title": "Choose player path that contain .map files"}
                self.settings['game_player_path'] = tkFileDialog.askdirectory(**opts)
            except ImportError:
                self.usage()
                exit(-1)
                
        if len(self.settings['game_player_path']) == 0:
            print "You must define the .map game path"
            exit(-1)
        self.map_files = self.read_folder(self.settings['game_player_path'])
        if len(self.settings['telnet_server']) == 0:
            if len(self.map_files) == 0:
                print "No .map files found in ", self.settings['game_player_path']
                exit(-1)
            self.create_tiles(self.map_files, self.settings['tile_path'], self.settings['tile_zoom'], self.settings['store_history'])
        else:
            print self.settings['GUI']
            if self.settings['GUI'] == "gui":
                th_addPoi = KFP_AddPOIGui(self)
            else: 
                th_addPoi = KFP_AddPOI(self)
            th_addPoi.start
            exit(-1)

    class MapReader:
        db = None
        store_history = False
        tiles_file_path = {}
        known_tiles = set()
        new_tiles = 0

        def __init__(self, database_directory, store_history):
            #threading.Thread.__init__(self)
            self.db = sqlite3.connect(os.path.join(database_directory, 'tile_history.db'))
            self.db.text_factory = str
            self.store_history = store_history
            self.db.execute("CREATE TABLE IF NOT EXISTS TILES(POS int,HASH int, T TIMESTAMP, data CHAR(512),"
                            " PRIMARY KEY(POS,HASH))")
            self.db.execute("CREATE TABLE IF NOT EXISTS VERSION as select 1 version")
            # Read already known index
            for record in self.db.execute("SELECT DISTINCT POS FROM TILES"):
                self.known_tiles.add(record[0])

        def is_tile_stored(self, index):
            return index in self.known_tiles

        def do_insert_tile(self, index, tile_hash):
            if self.store_history:
                # Check if the tile is not already in the db
                rs = self.db.execute("SELECT COUNT(*) CPT FROM TILES WHERE POS=? AND HASH=?", [index, tile_hash])
                if rs.fetchone()[0] == 0:
                    return True
                else:
                    return False
            else:
                return True

        def insert_tile(self, index, data, file_date):
            tile_hash = hash(data)
            if self.do_insert_tile(index, tile_hash):
                self.db.execute("INSERT INTO TILES VALUES (?,?,?,?)", [index, tile_hash, file_date, data])
                self.known_tiles.add(index)
                return True
            else:
                return False

        def fetch_tile(self, index):
            if not self.is_tile_stored(index):
                return None
            if self.store_history:
                data = self.db.execute("SELECT data FROM TILES WHERE POS=? ORDER BY T DESC LIMIT 1", [index]).fetchone()
                if not data is None:
                    return data[0]
                else:
                    return None
            else:
                data = self.db.execute("SELECT data FROM TILES WHERE POS=? LIMIT 1", [index]).fetchone()
                if not data is None:
                    return data[0]
                else:
                    return None

        def import_file(self, map_file, index_only):
            file_date = os.stat(map_file).st_mtime
            with open(map_file, "rb") as curs:
                # Check beginning of file
                if not curs.read(4) == "map\0":
                    print "Skip "+os.path.basename(map_file)+" wrong file header"
                    return
                curs.read(1)
                #######################
                # read index
                num = struct.unpack("I", curs.read(4))[0]
                # read tiles position
                tiles_index = [struct.unpack("i", curs.read(4))[0] for i in xrange(num)]
                #######################
                # read tiles pixels
                if not index_only:
                    curs.seek(524297)
                    for i in xrange(num):
                        if self.store_history or not self.is_tile_stored(tiles_index[i]):
                            # extract 16-bytes pixel 16*16 tile
                            tile_data = curs.read(512)
                            if len(tile_data) == 512:
                                if self.insert_tile(tiles_index[i], tile_data, file_date):
                                    self.tiles_file_path[tiles_index[i]] = map_file
                                    self.new_tiles += 1
                            else:
                                # Corrupted file
                                print "Skip "+os.path.basename(map_file)+" may be already used by another process"
                                break
                        else:
                            curs.seek(curs.tell() + 512)
                else:
                    self.tiles = dict.fromkeys(tiles_index + self.tiles.keys())
            self.db.commit()

    def create_tiles(self, player_map_path, tile_output_path, tile_level, store_history):
        """
         Call base tile and intermediate zoom tiles
        """
        if not os.path.exists(tile_output_path):
            os.mkdir(tile_output_path)
        self.create_base_tiles(player_map_path, tile_output_path, tile_level, store_history)
        self.create_low_zoom_tiles(tile_output_path, tile_level)
    # Convert X Y position to MAP file index
    def index_from_xy(self,x, y):
        return (y - 16) << 16 | (x & 65535)
    
    def create_base_tiles(self,player_map_path, tile_output_path, tile_level, store_history):
        """
        Read all .map files and create a leaflet tile folder
        @param player_map_path array of folder name where are stored map ex:C:\Users\UserName\Documents\7 Days To Die\Saves\
        Random Gen\lll\Player\76561197968197169.map
        @param tile_level number of tiles to extract around position 0,0 of map. It is in the form of 4^n tiles.It will
        extract a grid of 2**n tiles on each side. n=8 will give you an extraction of -128 +128 in X and Y tiles index.
        """
        reader = self.MapReader(tile_output_path, store_history)
        # Read and merge all tiles in .map files
        lastprint = 0
        for i, map_file in enumerate(player_map_path):
            if time.time() - lastprint > 1:
                print "Read map file ", os.path.basename(map_file), i + 1, "/", len(player_map_path)
                lastprint = time.time()
            try:
                reader.import_file(map_file, False)
            except struct.error:
                print "Skip "+os.path.basename(map_file)+" may be already used by another process"
        # make zoom folder
        z_path = os.path.join(tile_output_path, str(tile_level))
        if not os.path.exists(z_path):
            os.mkdir(z_path)
        #compute min-max X Y
        big_tile_range = 2**tile_level
        tile_range = big_tile_range*16
        # iterate on x
        minmax_tile = [(tile_range, tile_range),(-tile_range, -tile_range)]
        used_tiles = 0
        for x in range(2**tile_level):
            if time.time() - lastprint > 1:
                print "Write tile X:", x + 1, " of ", 2**tile_level
                lastprint = time.time()
            x_dir_make = False
            x_path = os.path.join(z_path, str(x - big_tile_range / 2))
            for y in range(2**tile_level):
                # Fetch 256 tiles
                big_tile = None
                # Combine two for loop into one
                for tx, ty in itertools.product(range(16), range(16)):
                    world_txy = (x * 16 + tx - tile_range / 2, y * 16 + ty - tile_range / 2)
                    tile_data = reader.fetch_tile(self.index_from_xy(world_txy[0], world_txy[1]))
                    if not tile_data is None:
                        used_tiles += 1
                        minmax_tile = [(min(minmax_tile[0][0], world_txy[0]), min(minmax_tile[0][1], world_txy[1])),
                                       (max(minmax_tile[1][0], world_txy[0]), max(minmax_tile[1][1], world_txy[1]))]
                        # Add this tile to big tile
                        # Create empty big tile if not exists
                        if big_tile is None:
                            big_tile = Image.new("RGB", (256, 256))
                        # convert image string into pil image
                        try:
                            tile_im = Image.frombuffer('RGB', (16, 16), tile_data, 'raw', 'BGR;15', 0, 1)
                            # Push this tile into the big one
                            big_tile.paste(tile_im, (tx * 16, ty * 16))
                        except ValueError:
                            print "The following file is corrupted, skip it:\n" +\
                                  reader.tiles_file_path.get(index_from_xy(world_txy[0], world_txy[1]))
                # All 16pix tiles of this big tile has been copied into big tile
                # Time to save big tile
                if not big_tile is None:
                    # Create Dirs if not exists
                    if not x_dir_make:
                        if not os.path.exists(x_path):
                            os.mkdir(x_path)
                            x_dir_make = True
                    png_path = os.path.join(x_path, str((big_tile_range - y) - big_tile_range / 2)+".png")
                    big_tile = ImageOps.flip(big_tile)
                    big_tile.save(png_path, "png")
        print "Min max tiles minx:", minmax_tile[0][0], " maxx:", minmax_tile[1][0],\
              "miny:", minmax_tile[0][1], " maxy: ", minmax_tile[1][1]
        print "Tiles used / total read", used_tiles, " / ", reader.new_tiles

    def create_low_zoom_tiles(self,tile_output_path, tile_level_native):
        """
            Merge 4 tiles of 256x256 into a big 512x512 tile then resize to 256x256
        """
        lastprint = 0
        for tile_level in range(tile_level_native, 0, -1):
            z_path = os.path.join(tile_output_path, str(tile_level))
            z_lower_path = os.path.join(tile_output_path, str(tile_level - 1))
            if not os.path.exists(z_lower_path):
                os.mkdir(z_lower_path)
            # list all X folders, convert to int then sort ascending
            tiles_to_process = set()
            x_paths = map(lambda x: int(x), os.listdir(z_path))
            for x_path in sorted(x_paths):
                for y_path in map(lambda y: int(y[:-4]), os.listdir(os.path.join(z_path, str(x_path)))):
                    tiles_to_process.add((x_path, y_path))
            while len(tiles_to_process) > 0:
                if time.time() - lastprint > 1:
                    print "Zoom level ",tile_level - 1, ", ", len(tiles_to_process), " tiles left"
                    lastprint = time.time()
                tile_to_process = next(iter(tiles_to_process))
                # compute id of origin tile
                orig_tile = (tile_to_process[0] - tile_to_process[0] % 2, tile_to_process[1] - tile_to_process[1] % 2)
                # compute the index of the 4 tiles
                tiles = [orig_tile, #bottom left
                         (orig_tile[0] + 1, orig_tile[1]), #bottom right
                         (orig_tile[0], orig_tile[1] + 1), #top left
                         (orig_tile[0] + 1, orig_tile[1] + 1)] #top right
                tiles_paste_pos = [(0, 0), (256, 0), (0, 256), (256, 256)]
                # Remove tiles from processing
                missing_tiles = set()
                for tile_index in tiles:
                    if tile_index in tiles_to_process:
                        tiles_to_process.remove(tile_index)
                    else:
                        missing_tiles.add(tile_index)
                lower_zoom_image = Image.new("RGB", (512, 512))
                for tile_index, paste_pos in zip(*[tiles, tiles_paste_pos]):
                    if tile_index not in missing_tiles:
                        # Compute path
                        tile_index_path = os.path.join(z_path, str(tile_index[0]), str(tile_index[1])+".png")
                        tile_im = Image.open(tile_index_path)
                        # Paste in big image
                        lower_zoom_image.paste(tile_im, paste_pos)
                # Dezoom the big tile
                lower_zoom_image = lower_zoom_image.resize((256, 256), Image.BICUBIC)
                # Save in lower zoom folder
                x_lower_path = os.path.join(z_lower_path, str(((orig_tile[0] + (2 ** tile_level) / 2) / 2)
                                                              - (2 ** (tile_level - 1)) / 2))
                if not os.path.exists(x_lower_path):
                    os.mkdir(x_lower_path)
                lower_zoom_image.save(os.path.join(x_lower_path, str(((orig_tile[1] + (2 ** tile_level) / 2) / 2)
                                                                     - (2 ** (tile_level - 1)) / 2) + ".png"))

    def read_folder(self,path):
        self.map_files = [os.path.join(path, self.file_name) for self.file_name in os.listdir(path) if self.file_name.endswith(".map")]
        self.map_files.sort(key=lambda file_path: -os.stat(file_path).st_mtime)
        return self.map_files

    def copyMapFile(self,path,value):
        shutil.copy(os.path.join(path,value),os.path.join("Map",value) )
        """    def copyMapFiles(self,path,value):
        shutil.copytree(os.path.join(path,value),os.path.join("Map",value) )
        """
    def usage(self):
        print "This program extract and merge map tiles of all players.Then write it in a folder with verious zoom"
        print " levels. In order to hide player bases, this program keep only the oldest version of each tile by default."
        print    " By providing the Server telnet address and password this software run in background and is able to do the"
        print    " following features:\n" 
        print    " - Update tiles when a player disconnect\n" 
        print    " - Add Poi when a whitelisted user say /addpoi title\n" 
        print    " - Update players csv coordinates file\n"
        print "Usage:"
        print "map_reader -g XX [options]"
        print " -g \"C:\\Users..\":\t The folder that contain .map files"
        print " -t \"tiles\":\t\t The folder that will contain tiles (Optional)"
        print " -z 8:\t\t\t\t Zoom level 4-n. Number of tiles to extract around position 0,0 of map." 
        print      " It is in the form of 4^n tiles.It will extract a grid of 2^n*16 tiles on each side.(Optional)"
        print " -s telnethost:port \t7DTD server ip and port (telnet port, default 8081) (Optional)"
        print " -p CHANGEME Password of telnet, default is CHANGEME (Optional)"
        print " -i True \t Do not read /addpoi command of players"
        print " -x True \t Do not write players track in csv files"
        print " -h 8080 Http Server Port(default 8081) (Optional)"
        print " -w \"C:\\...\\xml\\whitelist.xml\":\t\t Authorized users list path..."
        print " -k \"C:\\...\\xml\\POIList.xml\":\t\t POI list xml..."
        print " -v True \t\t\t\t Show received data (0=False, 1=True)..."
        print " -c \"www\":\t\t The folder that contain your index.html (Optional)"
        print " -newest Keep track of updates and write the last version of tiles. This will show players bases on map.(Optional)"
        print " -b gui:\t\t Use Gui version (Optional)"
        print " -f FTPHost:UserName:PassWord \t FTP server connection infos (Optional)"


    def run(self):
        pass
        
th1 = Advanced_MapReader()
th1.start()
th1.join()
