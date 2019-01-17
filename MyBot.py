#!/usr/bin/env python3

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants
from hlt.positionals import Direction

import random
import logging

# From https://www.youtube.com/watch?v=hgWaow7L9m8&index=4&list=PLQVvvaa0QuDcJe7DPD0I5J-EDKomQDKsz
# List of next positions the ships will take
next_moves = {}

ship_status = {}

# List of which ships have been given a move command
command_queue = []

# List of ships to move in order of priority; only includes returning ships
ship_order = []

def order_movements(player, game_map):
    distances = {}
    
    for ship in player.get_ships():
        if ship.id not in ship_status or ship_status[ship.id] != "returning":
            continue
        distances[ship.id] = game_map.calculate_distance(ship.position, player.shipyard.position)
    
    # https://stackoverflow.com/questions/20944483/python-3-sort-a-dict-by-its-values/20948781
    s = [(k, distances[k]) for k in sorted(distances, key=distances.get, reverse=False)]    
    for k, v in s:    
        ship_order.append(k)
#    logging.info("ship_order \n {}".format(ship_order) )
    return

    


# Doesn't count a space as occupied if a ship is moving from it
def for_real_occupied(position, player, game_map):
    # Occupied by another player?
    if (game_map[position].is_occupied and not player.has_ship(game_map[position].ship.id) ):
        return True
    # Return occupied if the ship hasn't moved yet or is staying still    
    # TODO: try to optimize movement by forcing the other ship to move first? This can be done by sorting the ships movement order by distance from dropoff points
    if game_map[position].is_occupied:
        id = game_map[position].ship.id
        if next_moves.keys() is None or id not in next_moves.keys() or next_moves.get(id) == position:
            return True        
    return False
    

def get_richest_direction(player, ship, game_map):
    # Can't move? Don't move!
    if ship.halite_amount < game_map[ship.position].halite_amount/10:
        direction = Direction.Still
        # Add the planned movement to the list
        command_queue.append(ship.move( direction ))
        next_moves[ship.id] = ship.position.directional_offset(direction)
        return direction
        
#    Inspired from https://www.youtube.com/watch?v=hgWaow7L9m8&index=4&list=PLQVvvaa0QuDcJe7DPD0I5J-EDKomQDKsz

#    directions = ["n", "s", "e", "w", "o"]
    directions = [Direction.North, Direction.South, Direction.East, Direction.West, Direction.Still]
    
    positions_list = ship.position.get_surrounding_cardinals()
    # halite_list is filled in same order as positions_list
    halite_list = []
    
    positions_list.append(ship.position)
    for pos in positions_list: #ship.position.get_surrounding_cardinals():
        halite_list.append(game_map[pos].halite_amount)
    # Weight the value of the current ship position to discourage unnecessary movement
    halite_list[-1] *= 2
    
    # TODO: Optimize?
    # Reject positions that are already being moved into.
    # Also reject positions that hold other ships
    for _ in range(0, len(positions_list)):
        for pos in positions_list:
            if pos in next_moves.values() or (for_real_occupied(pos, player, game_map) and pos != ship.position):# and (next_moves.get(game_map[pos].ship.id) is None or next_moves.get(game_map[pos].ship.id) == pos)):
                ind = positions_list.index(pos)
#                logging.info("ship {} remove position {} halite {} direction {}".format(ship.id, pos, halite_list[ind], directions[ind]) )
                positions_list.remove(pos)
                del halite_list[ind]
                del directions[ind]
                continue
#    logging.info("ship {} directions: ".format(ship.id, directions) )
    
#    for ship2 in player.get_ships():
#        logging.info("ship {} position {}".format(ship2.id, ship2.position) )
    
    best = max(halite_list)
    direction = directions[halite_list.index(best)]
    # Add the planned movement to the list
    command_queue.append(ship.move( direction ))
    next_moves[ship.id] = ship.position.directional_offset(direction)
    return direction
    #random.choice(["n", "s", "e", "w"])

def move_to_dropoff(player, ship, game_map):
    #TODO: probably shouldn't be returning to base anymore if cargo hold is empty
    if ship.halite_amount < game_map[ship.position].halite_amount/10:
        direction = Direction.Still
        # Add the planned movement to the list
        command_queue.append(ship.move( direction ))
        next_moves[ship.id] = ship.position.directional_offset(direction)
        return direction
        
    # TODO: incorporate dropoffs, not just shipyard
    # Derived from naive_navigate()
    for direction in game_map.get_unsafe_moves(ship.position, player.shipyard.position):
        target_pos = ship.position.directional_offset(direction)
        if (for_real_occupied(target_pos, player, game_map) and not player.has_ship(game_map[target_pos].ship.id) ) or (not for_real_occupied(target_pos, player, game_map) and (next_moves.values() is None or not target_pos in next_moves.values())):
    #        self[target_pos].mark_unsafe(ship)
            command_queue.append(ship.move(direction))
            # Add the planned movement to the list
            next_moves[ship.id] = ship.position.directional_offset(direction)
            return direction
        # Swap ships if possible.
        elif for_real_occupied(target_pos, player, game_map):
            other_ship = game_map[target_pos].ship
            if other_ship.halite_amount < ship.halite_amount and other_ship.halite_amount >= game_map[target_pos].halite_amount/10 and ship.halite_amount >= game_map[ship.position].halite_amount/10 and (next_moves.keys() is None or not other_ship.id in next_moves.keys()):
                opposite_direction = Direction.invert(direction)
                # move the other ship and keep track of it in the lists
                command_queue.append(other_ship.move( opposite_direction ))
                next_moves[other_ship.id] = ship.position

                command_queue.append(ship.move(direction))
                # Add the planned movement to the list
                next_moves[ship.id] = ship.position.directional_offset(direction)
                return direction
                
    command_queue.append(ship.stay_still())
    next_moves[ship.id] = ship.position
    return Direction.Still

#    direction = game_map.naive_navigate(ship, player.shipyard.position)
#    command_queue.append(ship.move( direction ))
#    next_moves[ship.id] = ship.position.directional_offset(direction)
#    return game_map.naive_navigate(ship, player.shipyard.position)



# This game object contains the initial game state.
game = hlt.Game()

# Respond with your name.
game.ready("MyPythonBot")

while True:
    # Reset positions list.
    next_moves = {}
    
    # Get the latest game state.
    game.update_frame()
    # You extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # A command queue holds all the commands you will run this turn.
    command_queue = []
    ship_order = []

    # Run two loops: first for returning ships and second for every other status.
    order_movements(me, game_map)

    for ship_id in ship_order:
        ship = me.get_ship(ship_id)
		# Don't do anything with a ship that's already moved (can occur during swapping)
        if not next_moves.keys() is None and ship.id in next_moves.keys():
            continue
      
        if ship.id not in ship_status:
            ship_status[ship.id] = "exploring"
            
        if ship_status[ship.id] == "returning":
            if ship.position == me.shipyard.position:
                ship_status[ship.id] = "exploring"
            else:
                move_to_dropoff(me, ship, game_map)
                continue
    

    for ship in me.get_ships():    
#        logging.info("Ship {} has {} halite.".format(ship.id, ship.halite_amount))
        
		# Don't do anything with a ship that's already moved (can occur during swapping)
        if not next_moves.keys() is None and ship.id in next_moves.keys():
            continue

        if ship.halite_amount >= constants.MAX_HALITE / 4:
            ship_status[ship.id] = "returning"
        
        # For each of your ships, move randomly if the ship is on a low halite location or the ship is full.
        #   Else, collect halite.
        if game_map[ship.position].halite_amount < constants.MAX_HALITE / 10 or ship.is_full:
            # Get the direction of the richest halite and move to it
            get_richest_direction(me, ship, game_map)

        else:
            next_moves[ship.id] = ship.position
            command_queue.append(ship.stay_still())

    # If you're on the first turn and have enough halite, spawn a ship.
    # Don't spawn a ship if you currently have a ship at port, though.
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and len(me.get_ships()) < 15 and ((for_real_occupied(me.shipyard.position, me, game_map) and not me.has_ship(game_map[me.shipyard.position].ship.id) ) or (not game_map[me.shipyard].is_occupied and not me.shipyard.position in next_moves.values())):
        command_queue.append(game.me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
#    logging.info("positions \n {}".format(next_moves.values()))
    game.end_turn(command_queue)
