#!/usr/bin/env python3

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants

import random
import logging

# From https://www.youtube.com/watch?v=hgWaow7L9m8&index=4&list=PLQVvvaa0QuDcJe7DPD0I5J-EDKomQDKsz
# List of next positions the ships will take
next_moves = []


def get_richest_direction(ship):
#     Inspired from https://www.youtube.com/watch?v=hgWaow7L9m8&index=4&list=PLQVvvaa0QuDcJe7DPD0I5J-EDKomQDKsz
    directions = ["n", "s", "e", "w", "o"]
    
    positions_list = ship.position.get_surrounding_cardinals()
    # halite_list is filled in same order as positions_list
    halite_list = []

    positions_list.append(ship.position)
    for pos in positions_list: #ship.position.get_surrounding_cardinals():
        halite_list.append(game_map[pos].halite_amount)
#        halite_dict[ len(halite_dict) ] = game_map[pos].halite_amount
    
#    halite_list.append(game_map[ship.position].halite_amount)
    
    for pos in positions_list:
    # Reject positions that are already being moved into.
    # Also reject positions that hold other ships
        if pos in next_moves or  (game_map[pos].is_occupied ): # and pos != ship.position
            ind = positions_list.index(pos)
            positions_list.remove(pos)
            del halite_list[ind]
            del directions[ind]
            
    
    best = max(halite_list)
    
    return directions[halite_list.index(best)]
    #random.choice(["n", "s", "e", "w"])


# This game object contains the initial game state.
game = hlt.Game()
ship_status = {}

# Respond with your name.
game.ready("MyPythonBot")

while True:
    # Reset positions list.
    next_moves = []

    # Get the latest game state.
    game.update_frame()
    # You extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # A command queue holds all the commands you will run this turn.
    command_queue = []

    for ship in me.get_ships():
        logging.info("Ship {} has {} halite.".format(ship.id, ship.halite_amount))
        if ship.id not in ship_status:
            ship_status[ship.id] = "exploring"

        if ship_status[ship.id] == "returning":
            if ship.position == me.shipyard.position:
                ship_status[ship.id] = "exploring"
            else:
                move = game_map.naive_navigate(ship, me.shipyard.position)
                command_queue.append(ship.move(move))
                continue
        elif ship.halite_amount >= constants.MAX_HALITE / 4:
            ship_status[ship.id] = "returning"
        
        # For each of your ships, move randomly if the ship is on a low halite location or the ship is full.
        #   Else, collect halite.
        if game_map[ship.position].halite_amount < constants.MAX_HALITE / 10 or ship.is_full:
            command_queue.append(ship.move( get_richest_direction(ship) ))
        else:
            command_queue.append(ship.stay_still())

    # If you're on the first turn and have enough halite, spawn a ship.
    # Don't spawn a ship if you currently have a ship at port, though.
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and len(me.get_ships()) < 15 and not game_map[me.shipyard].is_occupied:
        command_queue.append(game.me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)