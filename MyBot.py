#!/usr/bin/env python3

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants
from hlt.positionals import Direction
from hlt.positionals import Position

import random
import logging

# Add variables to these game stages as needed.
class Early_Game:
    # TODO: Have this vary depending on map size / number of players.
    max_ships = 10

class Late_Game:
    # We don't want to waste resources building ships when they won't be able to reach the mining areas.
    max_ships = 0

	# Last twenty rounds or so, defined by a variable further below.
class Endgame:
    max_ships = 0

# Initialize the game type
current_game = Early_Game()


# From https://www.youtube.com/watch?v=hgWaow7L9m8&index=4&list=PLQVvvaa0QuDcJe7DPD0I5J-EDKomQDKsz
# List of next positions the ships will take
next_moves = {}

# Target positions for aggressive ships
targets = {}

# Possible statuses:
# "exploring"	- mining
# "returning"	- returning with full load
# "crusader"	- aggressive
ship_status = {}

# List of which ships have been given a move command
command_queue = []

# List of ships to move in order of priority; only includes returning ships
ship_order = []

# Gets the closest dropoff to a ship.
# player does not have to be the ship owner!
def get_closest_dropoff(ship, player, game_map):
    distance = {}
    for p in player.get_dropoffs():
        distance[p] = game_map.calculate_distance(ship.position, p.position)
    distance[player.shipyard] = game_map.calculate_distance(ship.position, player.shipyard.position)
    
    distance_list = list(distance.values())
    distance_index = distance_list.index(min(distance_list))
    dropoff = list(distance.keys())[distance_index]    
    
    return dropoff
    
# Create a queue of which returning ships should move first.  Ships closest to a dropoff get priority.
# This allows for a more efficient stream of incoming ships to dropoffs.
def order_movements(player, game_map):
    distances = {}
    
	# dropoff is hardcoded to shipyard, since we don't actually create dropoffs... :)
	# TODO: allow for dropoffs
    for ship in player.get_ships():
        if ship.id not in ship_status or ship_status[ship.id] != "returning":
            continue
        distances[ship.id] = game_map.calculate_distance(ship.position, player.shipyard.position)
    
	# Sort the ships based on distance from dropoff
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
    if game_map[position].is_occupied:
        id = game_map[position].ship.id
        if next_moves.keys() is None or id not in next_moves.keys() or next_moves.get(id) == position:
            return True        
    return False
    

# Find the richest halite adjacent to the ship (including current tile)
# Moves the ship to the tile as well
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
    
	# Create a list of halite amounts, corresponding to the directions they are in
	# So halite_list[0] is the amount of halite in the north tile
	# positions_list will be used for collision detection
    positions_list = ship.position.get_surrounding_cardinals()
    
	# halite_list is filled in same order as positions_list
    halite_list = []
    
    positions_list.append(ship.position)
    for pos in positions_list: #ship.position.get_surrounding_cardinals():
        halite_list.append(game_map[pos].halite_amount)
    # Weight the value of the current ship position to discourage unnecessary movement
    halite_list[-1] *= 2
    
    # Reject positions that are already being moved into.
    # Also reject positions that hold other ships
    # TODO: Optimize?
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

	# Get the richest direction
    best = max(halite_list)
    direction = directions[halite_list.index(best)]
    # Add the planned movement to the list
    command_queue.append(ship.move( direction ))
    next_moves[ship.id] = ship.position.directional_offset(direction)
    return direction
    #random.choice(["n", "s", "e", "w"])


# Moves a ship to target position.  Different from naive_navigate in that it accounts for friendly ships' intended movements.
def move_to_target(position, player, ship, game_map):

    # Don't move if we've already reached the destination
    # Don't try to move if we don't have enough halite
    if position == ship.position or ship.halite_amount < game_map[ship.position].halite_amount/10:
        direction = Direction.Still
        # Add the planned movement to the list
        command_queue.append(ship.stay_still())#move( direction ))
        next_moves[ship.id] = ship.position.directional_offset(direction)
        return direction

    moves = game_map.get_unsafe_moves(ship.position, position)
    # Randomize the available moves to distribute the ships more evenly on the map
	random.shuffle(moves)
    for direction in moves:
        target_pos = ship.position.directional_offset(direction)
        # Go to tile if enemy is there and it's the end position
        # Go to tile if not occupied or going to be occupied
        if (for_real_occupied(target_pos, player, game_map) and not player.has_ship(game_map[target_pos].ship.id) and target_pos == position) or (not for_real_occupied(target_pos, player, game_map) and (next_moves.values() is None or not target_pos in next_moves.values())):
    #        self[target_pos].mark_unsafe(ship)
            command_queue.append(ship.move(direction))
            # Add the planned movement to the list
            next_moves[ship.id] = ship.position.directional_offset(direction)
            return direction
            
    # This should be unreachable
    return None
    

# Move to the closest dropoff to the ship
# player should be the ship owner, since you can't deposite on enemy dropoffs
def move_to_dropoff(player, ship, game_map):
    #TODO: probably shouldn't be returning to base anymore if cargo hold is empty
    if ship.halite_amount < game_map[ship.position].halite_amount/10:
        direction = Direction.Still
        # Add the planned movement to the list
        command_queue.append(ship.stay_still())#move( direction ))
        next_moves[ship.id] = ship.position.directional_offset(direction)
        return direction
        
    # TODO: incorporate dropoffs, not just shipyard
    # Derived from naive_navigate()
    moves = game_map.get_unsafe_moves(ship.position, player.shipyard.position)
	# Randomize the moves to evenly distribute the ships on the map
    random.shuffle(moves)
    for direction in moves:
        target_pos = ship.position.directional_offset(direction)
        # Crash into shipyard if near end of game
        # Go to tile if enemy is there
        # Go to tile if not occupied or going to be occupied
        if (type(current_game) is Endgame and game_map.calculate_distance(ship.position, player.shipyard.position) == 1 )  or (for_real_occupied(target_pos, player, game_map) and not player.has_ship(game_map[target_pos].ship.id) and target_pos == player.shipyard.position ) or (not for_real_occupied(target_pos, player, game_map) and (next_moves.values() is None or not target_pos in next_moves.values())):
            command_queue.append(ship.move(direction))
            # Add the planned movement to the list
            next_moves[ship.id] = ship.position.directional_offset(direction)
            return direction
        # Swap ships if possible, and if they are both friendlies.
        elif for_real_occupied(target_pos, player, game_map) and player.has_ship(game_map[target_pos].ship.id):
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

#	 Use this for debugging (basically naive_navigate with necessary bookwork)
#    direction = game_map.naive_navigate(ship, player.shipyard.position)
#    command_queue.append(ship.move( direction ))
#    next_moves[ship.id] = ship.position.directional_offset(direction)
#    return game_map.naive_navigate(ship, player.shipyard.position)



# This game object contains the initial game state.
game = hlt.Game()

# Respond with your name.
game.ready("Croissant")

# When endgame is activated
endgame_turn = constants.MAX_TURNS  - 20
# TODO: Base this on percentege of halite on map, and size of map.
late_game_turn = constants.MAX_TURNS  - 30
# TODO: Base this on size of map
crusade_turn = constants.MAX_TURNS  - 40

# The infinite loop that every true programmer loves
while True:
    # Reset positions list.
    next_moves = {}
    
    # Get the latest game state.
    game.update_frame()
    # Extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # command_queue holds all the commands that will run this turn.
    command_queue = []
	# Order to move returning ships only!  Other ships move afterward, in arbitrary order
    ship_order = []

    # Run two loops: first for returning ships and second for every other status.
	# Fill up ship_order
    order_movements(me, game_map)

    for ship_id in ship_order:
        ship = me.get_ship(ship_id)
		# Don't do anything with a ship that's already moved (can occur during swapping)
        if not next_moves.keys() is None and ship.id in next_moves.keys():
            continue
      
		# For newly created ships
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
        
		# Don't do anything with a ship that's already moved
        if not next_moves.keys() is None and ship.id in next_moves.keys():
            continue

		# Why have this in the second loop as well?  Because the first loop doesn't run if no ships are returning
        if ship.id not in ship_status:
            ship_status[ship.id] = "exploring"

		# Be mean and aggressive
        if ship_status[ship.id] == "crusader":
            move_to_target(targets[ship.id], me, ship, game_map)

        # If we've reached the end then there's no point in wandering around.
        elif type(current_game) is Endgame:
            break
        
        elif ship_status[ship.id] == "exploring":
            if ship.halite_amount >= constants.MAX_HALITE * (4.0/5.0):
                ship_status[ship.id] = "returning"                
        
            # For each of your ships, move towards the immediate richest halite (may be current tile)
            elif game_map[ship.position].halite_amount < constants.MAX_HALITE / 10 or ship.is_full:
                # Get the direction of the richest halite and move to it
                get_richest_direction(me, ship, game_map)

        else:
            next_moves[ship.id] = ship.position
            command_queue.append(ship.stay_still())


    # If you have enough halite and satisfy an endless number of constraints, spawn a ship.
	# Spawn if below max ship number
	# Spawn if an enemy is blocking the shipyard (we're probably going to end up losing a ship one way or another anyway)
	# Spawn if the shipyard is not occupied by a friendly ship
    if me.halite_amount >= constants.SHIP_COST and len(me.get_ships()) < current_game.max_ships and ((for_real_occupied(me.shipyard.position, me, game_map) and not me.has_ship(game_map[me.shipyard.position].ship.id) ) or (not game_map[me.shipyard].is_occupied and not me.shipyard.position in next_moves.values())):
        command_queue.append(game.me.shipyard.spawn())

    # Check for late game
    if game.turn_number == late_game_turn:
        current_game = Late_Game()

    # Check for crusade era
    if game.turn_number == crusade_turn:
        # Find the richest player to torment
        player = 0
        player_halite = {}
        for p in game.players.values():
            if p is not game.me:
                player_halite[p] = p.halite_amount
        
        halite_list = list(player_halite.values())
        player_index = halite_list.index(max(halite_list))
        player = list(player_halite.keys())[player_index]
                
#        logging.info("player is {}".format(player))

        # Start a crusade
        for ship in me.get_ships():
            dropoff = get_closest_dropoff(ship, player, game_map)
            # Only the most worthless ships can join this crusade
			# If they have cargos less than half full
			# If they are close enough to an enemy dropoff to make it
			# If there not already 6 ships crusading
			# TODO: remove number constraint, and replace infinite loop with a 10 for loop
            if ship.halite_amount < constants.MAX_HALITE / 2.0 and game_map.calculate_distance(ship.position, dropoff.position) < constants.MAX_TURNS - (game.turn_number + 10) and len(targets.values()) < 6: 
                # Target a location near the closest enemy dropoff
                yard = dropoff.position
                location = yard
                while location == yard or (targets.values() is not None and location in targets.values()):
                    #logging.info("location is {}".format(location))
                    #logging.info("locations are {}".format(targets))
                    location = Position(yard.x, yard.y + random.randrange(-3,4,1) ) 
				# Set the target location
                targets[ship.id] = location
                ship_status[ship.id] = "crusader"
#        logging.info("targets are {}".format(targets))


 	# If at endgame, toggle it and send the ships home.  Crusading ships continue their noble work
    if game.turn_number == endgame_turn:
        current_game = Endgame()

        for ship in me.get_ships():
            # The crusaders aren't coming back :)
            if ship_status[ship.id] != "crusader":
                ship_status[ship.id] = "returning"

    # Send your moves back to the game environment, ending this turn.
#    logging.info("positions \n {}".format(next_moves.values()))
    game.end_turn(command_queue)
