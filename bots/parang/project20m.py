r'''Project20M - A Python version of Project20M
    Copyright (C) 2004-2008  Andrew Huff, Vincent Chan, Laurence Tondelier,
    Damian Bundred, Colm Egan, and Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from random import random

from parlance.config    import VerboseObject
from parlance.gameboard import Unit
from parlance.orders    import *
from parlance.player    import Player
from parlance.tokens    import AMY, FLT, SPR, SUM, WIN

class Project20M(Player):
    ''' A clone of Andrew Huff's bot.
        This class is approximately equivalent to Project20M's PrimeMinister.
        Most of the functionality of the PrimeMinister and Project20M
        java classes are already included in Player or Client.
    '''#'''
    
    def handle_HLO(self, message):
        self.__super.handle_HLO(message)
        if self.power:
            self.map.us = self.power
            self.t = Tactics(self.map)
        self.log_debug(7, "Game Started, you are playing %s, "
                "your passcode is %d", self.power.name, self.pcode)
    def generate_orders(self):
        # Called by handle_NOW in its own thread.
        # Expected to create and submit an order set.
        turn = self.map.current_turn
        phase = turn.phase()
        
        self.log_debug(7, "PrimeMinister: *************** Season %s"
                " **************** ", turn.season)
        self.t.valueProvinces()  # update tactic values
        
        # WIN (inside NOW)
        #-----------------------------------
        if phase == turn.build_phase:
            # if it is winter then need to carry out any adjustments
            # (builds and disbands)
            orders = self.t.adjustments()
            self.sendOrders(orders)
        
        # SUM, AUT (inside NOW)
        #-----------------------------------
        elif phase == turn.retreat_phase:
            # if it is summer or autumn then need to carry out any retreats
            # we are given a list of where all the units are, with some having
            # a (possibly empty) list of places they have to retreat to
            orders = []
            for unit in self.power.units:
                self.log_debug(7, "busy loop here?")
                if unit.dislodged:
                    orders.append(self.getRetreat(unit))
            self.sendOrders(orders)
        elif phase == turn.move_phase:
            # if it is spring or fall then need a Negotiator thread to listen
            # to proposals
            # PrimeMinister needs to schedule a SendOrdersTask to ensure
            # orders are eventually sent
            n = Coordinator(self.map, self.t)
            # should it value the provinces here?
            theOrders = n.coordinateUnits()
            self.sendOrders(theOrders)
    def handle_SCO(self, message):
        if self.in_game and self.power:
            self.log_debug(7, "We have %d supply centers.",
                    len(self.power.centers))
    def getRetreat(self, thisUnit):
        self.log_debug(7, "PrimeMinister: suggesting retreat for unit in %s",
                thisUnit.coast.province.name)
        retreatTos = [self.map.coasts[key]
                for key in thisUnit.coast.borders_out
                if key[1] in thisUnit.retreats]
        return self.t.getBestRetreat(thisUnit, retreatTos)
    def sendOrders(self, orders):
        if orders:
            self.log_debug(7, "PrimeMinister: Final Orders")
            order_set = OrderSet(self.power)
            for order in orders:
                self.log_debug(7, order)
                order_set.add(order)
            self.submit_set(order_set)
            self.log_debug(7, "PrimeMinister: Orders sent")
        else:
            self.log_debug(7, "PrimeMinister: No orders to send")

class Tactics(VerboseObject):
    #*************************** public functions ****************************#
    def __init__(self, board):
        self.__super.__init__()
        self.map = board
        # the independent orders we generated last turn
        self.lastTurnsOrders = []
        for coast in board.coasts.values():
            coast.basicValue = [0] * Constants.numberIterations
            coast.connections = [board.coasts[key]
                for key in coast.borders_out]
        for coast in board.coasts.values():
            coast.landConnections = sum([c.connections
                    for c in coast.province.coasts if c.unit_type is AMY], [])
            coast.seaConnections = sum([c.connections
                    for c in coast.province.coasts if c.unit_type is FLT], [])
    
    def valueProvinces(self):
        # sets overall value for each province
        self.enumerateValues()
    
    def getBestOrders(self):
        # find a list of best independent orders for all our units
        return self.createOrders()
    
    def getNextBestOrder(self, order):
        # return the next best order this unit could do, after the given order
        orders = self.getValidOrders(order.unit)
        filteredOrders = self.filter(orders)
        bestOrder = None
        bestScore = -9999999
        for possibleOrder in filteredOrders:
            thisScore = evaluate(possibleOrder, self.map)
            if bestScore < thisScore < evaluate(order, self.map):
                # point best order so far to this one
                bestOrder = possibleOrder
                # set highest score so far to this one
                bestScore = thisScore
        if not bestOrder:
            for possibleOrder in orders:
                thisScore = evaluate(possibleOrder, self.map)
                if bestScore < thisScore < evaluate(order, self.map):
                    # point best order so far to this one
                    bestOrder = possibleOrder
                    # set highest score so far to this one
                    bestScore = thisScore
        if not bestOrder:
            self.log_debug(7, "getNextBestOrder returned null!? "
                    "Returning a hold")
            bestOrder = HoldOrder(order.unit)
        return bestOrder
    
    def adjustments(self):
        # return a list of Build orders, or a list of Remove orders
        numberBuilds = len(self.map.us.centers) - len(self.map.us.units)
        if numberBuilds > 0:
            self.log_debug(7, "Suggesting builds")
            return self.suggestBuilds(numberBuilds)
        elif numberBuilds < 0:
            self.log_debug(7, "Suggesting removes")
            return self.suggestRemoves(-numberBuilds)
        else: return None  # no adjustments to make
    
    def getBestRetreat(self, unit, canRetreatTo):
        retreatOrders = []
        for thisPlace in canRetreatTo:
            if not thisPlace.province.units:
                # we might have retreated another unit to there
                retreatOrders.append(RetreatOrder(unit, thisPlace))
        if not retreatOrders:
            return DisbandOrder(unit)
        retreatOrders.sort(self.compareTo)
        bestRetreat = retreatOrders[0]
        # assume there's a unit there now
        target(bestRetreat).units.append(unit)
        self.log_debug(7, "retreating with: %s", bestRetreat)
        return bestRetreat
    
    def removeDuplicates(self, l):
        result = []
        for item in l:
            if item not in result:
                result.append(item)
        return result
    
    #************************** private functions ****************************#
    
    def enumerateValues(self):
        # updates those all-important provincial values in the map depending
        # on the season
        if self.map.current_turn.season in (SPR, SUM, WIN):
            # update those all-important provincial values in the GPD
            self.setBasicValues(Constants.spring_defence_weight,
                    Constants.spring_attack_weight)
            # update the strength and competition values in the GPD
            self.setStrengthAndCompetitionValues()
            # use basic strength and competition values to calculate an
            # overall value for each province
            self.setFinalValues(Constants.spring_iteration_weight,
                    Constants.spring_strength_weight,
                    Constants.spring_competition_weight)
        else: # season must be "FAL" or "AUT"
            # updates those all-important provincial values in the GPD
            self.setBasicValues(Constants.autumn_defence_weight,
                    Constants.autumn_attack_weight)
            # update the strength and competition values in the GPD
            self.setStrengthAndCompetitionValues()
            # use basic strength and competition values to calculate an
            # overall value for each province
            self.setFinalValues(Constants.autumn_iteration_weight,
                    Constants.autumn_strength_weight,
                    Constants.autumn_competition_weight)
        # self.map.printMap(self.map.us+".csv")
    
    def setBasicValues(self, defence_weight, attack_weight):
        # the basic value is found as follows
        # 1) every province is given a basicValue[0] where
        #    basicValue[0] = size of strongest adjacent power * weighting for
        #        supply centres that are under our control
        #    basicValue[0] = size of owning power for supply centres under
        #        enemy control
        #    basicValue[0] = 0 in all other situations
        # 2) basicValue[0..n] are calculated iteratively, where
        #    basicValue[i] for a province is the sum of basicValue[i-1] for
        #        each adjacent province added to basicValue[i-1] for current
        #        province
        
        # sets the basicValue[0] in each province for spring
        self.calculateInitialValues(defence_weight, attack_weight)
        # iterates up to basicValue[n] in each province FOR NOW SET TO 10
        self.iterateValues(Constants.numberIterations)
    
    def setStrengthAndCompetitionValues(self):
        # the strength and competition values are found as follows
        # Strength value for a province = number of units we have that can
        #     move into this province next turn
        # Competition value for a province = greatest number of units any
        #     other power has that can move into this province next turn
        
        for theProvince in self.map.spaces.values():
            # for each province
            powers = self.map.powers.keys()
            numbers = getNumberOfAdjacentUnits(theProvince, powers, self.map)
            for i in range(len(powers)):
                if powers[i] == self.map.us:
                    theProvince.strength = numbers[i]
                    numbers[i] = 0
            numbers.sort()
            theProvince.competition = numbers[-1]
    
    def setFinalValues(self, iteration_weight,
            strength_weight, competition_weight):
        # this function finds final Value for each Place
        for thePlace in self.map.coasts.values():
            thePlace.Value = 0
            for j in range(Constants.numberIterations):
                thePlace.Value += thePlace.basicValue[j] * iteration_weight[j]
    
    def calculateInitialValues(self, defence_weight, attack_weight):
        # this function finds basicValue[0] for each place
        for theProvince in self.map.spaces.values():
            if theProvince.is_supply(): # if it's a supply centre
                if not theProvince.owner: # and it's neutral
                    theProvince.basicValue = (self.getWeakestPower()
                            * attack_weight)
                else:
                    if theProvince.owner == self.map.us: # if it belongs to us
                        # set value to strongest adjacent power
                        theProvince.basicValue = (
                                strongestAdjacentOpponentStrength(theProvince,
                                    self.map) * defence_weight)
                    else:  # it belongs to an opponent
                        # set value to strength of owner
                        ownerStrength = getStrength(theProvince.owner)
                        theProvince.basicValue = ownerStrength * attack_weight
                if self.map.us in theProvince.homes:
                    # if it's a home/build centre for us, its worth more
                    theProvince.basicValue *= 1.1; # constant alert!
            else: # it isn't a supply centre
                # set value to 0
                theProvince.basicValue =  0
            
            # finally, if the province has any coasts, set their values to the
            # values of the province
            for thisCoast in theProvince.coasts:
                thisCoast.basicValue[0] = theProvince.basicValue
    
    def getAveragePower(self):
        averagePower = 0
        for iterator in self.map.powers.values():
            averagePower += getStrength(iterator)
        averagePower /= len(self.map.powers)
        return averagePower
    
    def getWeakestPower(self):
        iterator = self.map.powers.itervalues()
        thisPower = iterator.next()
        weakestPower = getStrength(thisPower)
        for thisPower in iterator:
            if getStrength(thisPower) < weakestPower:
                weakestPower = getStrength(thisPower)
        return weakestPower
    
    def iterateValues(self, n):
        # this function iterates up to basicValue[n] for each place
        allPlaces = self.map.coasts.values()
        for i in range(1, n):
            # for each iteration
            for thePlace in allPlaces:
                # for each place
                thePlace.basicValue[i] = 0
                landConnections = thePlace.landConnections
                seaConnections = thePlace.seaConnections
                
                if thePlace.unit_type is AMY:
                    # if this place is not out at sea
                    canGetToByConvoy = []
                    for seaConnection in seaConnections:
                        if (seaConnection.province.units and
                                seaConnection.province.unit.can_convoy()):
                            # this Fleet could convoy us somewhere
                            for couldConvoyTo in seaConnection.seaConnections:
                                # for each place that fleet could move to
                                beach = couldConvoyTo.province.is_coastal()
                                if beach and beach not in landConnections:
                                    canGetToByConvoy.append(beach)
                    canGetToByConvoy = self.removeDuplicates(canGetToByConvoy)
                    for thisConnection in canGetToByConvoy:
                        thePlace.basicValue[i] += self.map.coasts[
                            thisConnection].basicValue[i-1] * 0.05; # constant!
                
                for thisConnection in landConnections:
                    if thePlace.unit_type is thisConnection.unit_type:
                        thePlace.basicValue[i] += thisConnection.basicValue[i-1]
                    elif thisConnection not in seaConnections:
                        thePlace.basicValue[i] += ( # constant!
                                thisConnection.basicValue[i-1] * 0.001)
                for thisConnection in seaConnections:
                    if thePlace.unit_type is thisConnection.unit_type:
                        thePlace.basicValue[i] += thisConnection.basicValue[i-1]
                    elif thisConnection not in landConnections:
                        thePlace.basicValue[i] += ( # constant!
                                thisConnection.basicValue[i-1] * 0.02)
                thePlace.basicValue[i] += thePlace.basicValue[i-1]
                thePlace.basicValue[i] /= Constants.iteration_army_divisor
    
    def createOrders(self):
        # this function uses the overall values for each province to find each
        # units best move independent of any other move decisions
        # basically they find all the provinces they could move to
        # (including places they could move to by convoy (including being
        # convoyed by the enemy))
        # then they move to the best one (or hold if it's already in the best
        # place it can immediately get to)
        
        orders = []
        allOurUnits = self.map.us.units
        self.log_debug(11, "******* creating basic orders")
        for theUnit in allOurUnits:
            order = self.getBestOrder(theUnit)
            orders.append(order)
            self.log_debug(11, "basic order: %s", order)
        self.log_debug(11, "******* finished creating basic orders")
        self.lastTurnsOrders = orders
        return orders
    
    def filter(self, orders):
        # filters the list of orders a unit can do
        # to remove stupid ones
        
        # it can move into or stay in valuable places
        filteredOrders = []
        for thisOrder in orders:
            if isValuable(target(thisOrder), self.map):
                # if it's an enemy supply centre, or a threatened one of ours
                filteredOrders.append(thisOrder)
        # If it's SPR it can also move into / stay in places within 1 move of
        # a valuable place
        if self.map.current_turn.season is SPR:
            for thisOrder in orders:
                withinTwo = thisOrder.destination.connections
                if self.hasValuable(withinTwo):
                    # if withinTwo contains a valuable place,
                    # add it to filteredAdjacents
                    filteredOrders.append(thisOrder)
        if not filteredOrders:
            # if none of the orders made it through the filtering, then let it
            # choose the best from all its orders
            filteredOrders.extend(orders)
        return filteredOrders
    
    def getBestOrder(self, u):
        # get the best order for this unit
        
        # hold, all its moves, and all its MoveByConvoys
        orders = self.getValidOrders(u)
        
        # Now filter the orders.
        filteredOrders = self.filter(orders)
        filteredOrders.sort(self.compareTo)
        bestOrder = filteredOrders[0]
        for order in orders:
            self.log_debug(12, "%s: %s %s %s", order,
                    evaluate(order, self.map),
                    order in filteredOrders,
                    order in self.lastTurnsOrders)
        if bestOrder in self.lastTurnsOrders:
            # should choose the next best order with some random probability
            if len(filteredOrders) > 1 and random() > 0.9:
                # 10% probability
                self.log_debug(7,
                        "RANDOM: CHOOSING THE 2ND BEST ORDER FOR %s", u)
                bestOrder = filteredOrders[1]
        
        # a little hack... if the bestOrder is to hold on a province we own,
        # threatened by just 1 enemy, move into where he is
        if (isinstance(bestOrder, HoldOrder) and
                target(bestOrder).owner == self.map.us):
            # if the order is to hold on a province we own
            
            # if there's a supply centre we don't own and it's within reach,
            # move there
            for thisPlace in canMoveTo(bestOrder.unit):
                if (thisPlace.province.is_supply() and
                        thisPlace.province.owner != self.map.us):
                    bestOrder = MoveOrder(u, thisPlace)
                    return bestOrder
            
            surroundingUnits = getSurroundingUnits(target(bestOrder), self.map)
            if len(surroundingUnits) == 1:
                # if there's just one enemy unit around us
                location = surroundingUnits[0].coast
                if location in canMoveTo(u):
                    # if we can move into where he is
                    self.log_debug(7, "%s IS HOLDING ON A SUPPLY CENTRE "
                            "ONLY THREATENED BY %s", u, surroundingUnits[0])
                    self.log_debug(7, "SO IT IS MOVING INTO %s",
                            surroundingUnits[0].coast)
                    bestOrder = MoveOrder(u, surroundingUnits[0].coast)
        
        return bestOrder
    
    def hasValuable(self, places):
        # returns true iff any of the places is a supply centre we don't own,
        # or a supply centre we own which is under threat
        for place in places:
            if isValuable(place.province, self.map):
                return True
        return False
    
    def getBestBuild(self):
        # pre: assumes the provinces are valued
        ownedBuildCentres = self.getOwnedBuildCentres(); # getCanBuild
        canBuild = []
        for thisProvince in ownedBuildCentres:
            # only if there isn't a unit there can we build there
            if not thisProvince.units:
                canBuild.append(thisProvince)
        if not canBuild:
            return WaiveOrder(self.map.us)
        bestSoFar = BuildOrder(Unit(self.map.us, canBuild[0].coasts[0]))
        for thisProvince in canBuild:
            for thisCoast in thisProvince.coasts:
                newArmy = BuildOrder(Unit(self.map.us, thisCoast))
                if evaluate(newArmy, self.map) > evaluate(bestSoFar, self.map):
                    bestSoFar = newArmy
        return bestSoFar
    
    def suggestBuilds(self, numberBuilds):
         builds = []
         for i in range(numberBuilds):
             # probably don't have to check if its coastal before building
             # a fleet, as if it isn't coastal
             # fleet score should be less than army score because it has no
             # connections
             self.valueProvinces()
             bestBuild = self.getBestBuild()
             if isinstance(bestBuild, BuildOrder):
                 # add that unit to the map
                 bestBuild.unit.build()
             builds.append(bestBuild)
         return builds
    
    def getBestRemove(self):
        # pre: assumes we have at least 1 unit to remove
        #      and that the provinces have been valued
        ourUnits = self.map.us.units
        bestSoFar = RemoveOrder(ourUnits[0])
        for iterator in ourUnits:
            newRemove = RemoveOrder(iterator)
            if evaluate(newRemove, self.map) > evaluate(bestSoFar, self.map):
                bestSoFar = newRemove
        return bestSoFar
    
    def suggestRemoves(self, numRemoves):
        removes = []
        for i in range(numRemoves):
            self.valueProvinces()
            bestRemove = self.getBestRemove()
            # remove that unit from the map
            bestRemove.unit.die()
            removes.append(bestRemove)
        return removes
    
    def suggestRetreat(self, u, retreatTos):
        self.log_debug(7, "Tactics: Suggesting Retreats")
        # pseudocode for working out retreats:
        # bug: two units might compete for the same place to retreat to, which
        # one should get it? Currently whichever one gets picked first. but it
        # should be the one with the highest 2nd best place to retreat to.
        # Keep the algorithm as it is unless this becomes a problem (or you
        # can think up a way of solving the problem)
        #
        # t = a temporary list of all the supply centres we can build in we own
        
        #  r = list of places this unit could retreat to
        #  if this is a winter retreat and the dumbot_value of the highest
        #  valued build-centre in "t" is higher than the highest valued place
        #  in "r",
        #      disband the unit
        #      and remove the highest valued build centre from "t"
        #  otherwise
        #    retreat to the place in "r" with the highest dumbbot_value
        
        canBuildAts = self.getOwnedBuildCentres()
        decisions = []  # a list of Orders
        
        highestValuedRetreat = retreatTos[0]
        retreatValue = highestValuedRetreat.Value
        for retreatTo in retreatTos[1:]:
            self.log_debug(7, "Tactics: considering retreat to %s", retreatTo)
            thisValue = retreatTo.Value
            if thisValue > retreatValue:
                highestValuedRetreat = retreatTo
                retreatValue = thisValue
        self.log_debug(7, "Tactics: HighestValuedRetreat = %s",
                highestValuedRetreat.name)
        
        if self.map.current_turn.season is WIN:
            # a winter retreat, so consider disbanding and building elsewhere
            highestValuedBuild = BuildOrder(Unit(self.map.us,
                    canBuildAts[0].coasts[0]))
            # 0 as have to check fleet in first location
            for canBuildAt in canBuildAts:
                for thisCoast in canBuildAt.coasts:
                    possibleBuild = BuildOrder(Unit(self.map.us, thisCoast))
                    if (evaluate(possibleBuild, self.map) >
                            evaluate(highestValuedBuild, self.map)):
                        highestValuedBuild = possibleBuild
            highestValued = canBuildAts[0]
            for thisProvince in canBuildAts:
                #if thisProvince.value > highestValued.value:
                #    highestValued = thisProvince
                pass
            if evaluate(highestValuedBuild, self.map) >= retreatValue:
                highestValuedBuild.unit.build()
                decisions.append(DisbandOrder(u))
                decisions.append(highestValuedBuild)
            else:
                decisions.append(MoveOrder(u, highestValuedRetreat))
        else: # not winter, must retreat
            decisions.append(RetreatOrder(u, highestValuedRetreat))
        return decisions
    
    def getValidOrders(self, unit):
        validOrders = []
        validOrders.append(HoldOrder(unit))
        for key in unit.coast.borders_out:
            validOrders.append(MoveOrder(unit, self.map.coasts[key]))
        if unit.can_be_convoyed():
            # now add all the MoveByConvoys it could do :-o
            # BUG: only adds convoys through 1 sea province
            for key in unit.coast.province.borders_out:
                seaConnection = self.map.spaces[key]
                if seaConnection.units and seaConnection.unit.can_convoy():
                    # this Fleet could convoy us somewhere
                    for place in seaConnection.borders_out:
                        # for each place that fleet could move to
                        couldConvoyTo = self.map.spaces[place].is_coastal()
                        if couldConvoyTo:
                            seaProvinces = [seaConnection.unit]
                            validOrders.append(ConvoyedOrder(unit,
                                self.map.coasts[couldConvoyTo], seaProvinces))
        return validOrders
    
    def getOwnedBuildCentres(self):
        # returns the list of all the provinces this power owns and can build
        # in
        return [self.map.spaces[home] for home in self.map.us.homes
                if home in self.map.us.centers]
    
    # Returns negative if this order is worth less than the given order,
    # 0 if they're worth the same
    # and positive if this order is better than the specified order.
    # BUT we're actually doing this the other way round, so that when
    # we use the built-in list sorting function it sorts them from high to low
    def compareTo(self, this, o):
        return int(evaluate(o, self.map) - evaluate(this, self.map))

class Coordinator(VerboseObject):
    #*************************** public functions ****************************#
    
    def __init__(self, board, tactics):
        self.__super.__init__()
        self.map = board
        self.tactics = tactics
        self.wantedOrders = []
    
    def coordinateUnits(self, weDo=None, theyDo=None):
        if not weDo:
            weDo = []
        elif not isinstance(weDo, list):
            weDo = [weDo]
        if not theyDo:
            theyDo = []
        elif not isinstance(theyDo, list):
            theyDo = [theyDo]
        
        # PRE: assumes that the provinces have been valued
        #      weDo is a list of Orders we promised to do
        #      theyDo is a list of Orders other players promised to do
        # POST: returns a list of orders our units should do
        
        self.wantedOrders = []
        # get the units' best individual orders
        orderList = self.tactics.getBestOrders()
        
        # set the orders we've promised to do
        for order in weDo:
            if order:
                order.helping = order.orderToSupport
                self.changeOrder(order.unit, order, orderList)
        
        for order in orderList: # set the units as having these orders
            order.unit.order = order
        self.log_debug(11, "**** coordinating units ****")
        # sort the orderList from most valuable to least
        orderList.sort(self.tactics.compareTo);
        for i in range(len(orderList)):
            orderList = self.coordinateUnit(orderList, i, theyDo)
        self.log_debug(11, "**** finished coordinating units ****")
        return orderList
    
    def getWantedOrders(self):
        # returns the list of orders we would like other people to do
        # pre: assumes that coordinate units has been run
        self.log_debug(7, "******wantedOrders:")
        i = 0
        while i < len(self.wantedOrders):
            order = self.wantedOrders[i]
            if (isinstance(order, SupportMoveOrder)
                    and target(order).units
                    and target(order).unit.nation ==
                        order.unit.nation):
                # we're asking someone to support a move into where they have
                # a unit, which is silly
                self.wantedOrders.pop(i)
            else:
                self.log_debug(7, order)
                i += 1
        self.log_debug(7, "*******************")
        return self.wantedOrders
    
    #************************** private functions ****************************#
    
    def coordinateUnit(self, orderList, i, theyDo):
        # coordinates the unit at index i in orderList
        order = orderList[i]; # for each order in the orderList
        self.log_debug(11, "looking at %s", order)
        
        # units which are avaliable to help order
        avaliables = self.getUnitsAvaliable(orderList, i)
        
        # should first check it will be able to get any essential help it may
        # need
        
        # if there's somebody whose order's destination is the same as ours,
        # try to get them to go somewhere else
        for clash in orderList:
            if (clash is not order and target(clash) == target(order)):
                self.log_debug(12, "%s clashes with %s", order, clash)
                outOfWay = self.getBestOutOfTheWayOrder(clash.unit, orderList)
                if clash.unit in avaliables and outOfWay:
                    orderList = self.changeOrder(clash.unit,
                            outOfWay, orderList)
                    self.log_debug(11, "%s agrees to do %s",
                            outOfWay.unit, outOfWay)
                else:
                    nextBestOrder = self.tactics.getNextBestOrder(order)
                    orderList = self.changeOrder(order.unit,
                            nextBestOrder, orderList)
                    self.log_debug(11, "changing to %s because of %s",
                            nextBestOrder, clash)
                    orderList = self.coordinateUnit(orderList, i, theyDo)
                    return orderList
        
        # alsoAvaliable are units which are avaliable so long as the help they
        # give doesn't require them to move
        alsoAvaliables = self.getUnitsAlsoAvaliable(orderList, i)
        # puts all the units in alsoAvaliable at the front of the list
        avaliables = alsoAvaliables + avaliables
        
        if isinstance(order, ConvoyedOrder):
            needed = order.path[0]
            if needed in avaliables:
                # if the unit we need to convoy us is avaliable, get it to do
                # the convoy
                newOrder = ConvoyingOrder(needed, order.unit,
                        order.destination)
                newOrder.helping = order
                orderList = self.changeOrder(needed, newOrder, orderList)
                self.log_debug(11, "%s agrees to do %s", needed, newOrder)
            else:
                if needed.nation != self.map.us:
                    wantedOrder = ConvoyingOrder(needed, order.unit,
                            order.destination)
                    wantedOrder.helping = order
                    self.wantedOrders.append(wantedOrder)
                nextBestOrder = self.tactics.getNextBestOrder(order)
                orderList = self.changeOrder(order.unit,
                        nextBestOrder, orderList)
                self.log_debug(11, "Couldn't get the convoy orders done, "
                        "so now doing %s", nextBestOrder)
                orderList = self.coordinateUnit(orderList, i, theyDo)
                return orderList
        
        supportsNeeded = getSupportsNeeded(order, self.map)
        self.log_debug(11, "%d supports needed", supportsNeeded)
        if (isinstance(order, MoveOrder) and target(order).units
                and target(order).unit.nation == self.map.us):
            supportsNeeded = 0
            self.log_debug(11, "But we're not going to ask for any support "
                    "as we're following one of our units")
        
        couldGiveSupport = couldBeSupportedBy(order, self.map)
        for couldHelp in couldGiveSupport:
            if supportsNeeded <= 0: break
            self.log_debug(11, "%s could support us...", couldHelp)
            if couldHelp in avaliables:
                self.log_debug(11, "%s will support us", couldHelp)
                # avaliable unit supporting order
                supportOrder = self.Support(couldHelp, order)
                supportOrder.helping = order
                orderList = self.changeOrder(couldHelp,
                        supportOrder, orderList)
                avaliables.remove(couldHelp)
                supportsNeeded -= 1 # this shouldn't strictly be here
            elif couldHelp.nation != self.map.us:
                # BUG: it should only ask for this if there are units
                # attacking here that don't belong to couldHelp.owner
                # otherwise, it should ask for couldHelp to NOT move into
                # order.destination
                
                # avaliable unit supporting order
                wantedOrder = self.Support(couldHelp, order)
                wantedOrder.helping = order
                self.wantedOrders.append(wantedOrder)
        return orderList
    
    def evaluate(self, orderList):
        # works out how good a set of orders are for us
        value = 0
        for order in orderList:
            value += evaluate(order, self.map)
            if (isinstance(order, SupportOrder) and
                    order.supported.nation == self.map.us):
                # constant alert!
                value += 0.75 * evaluate(order.orderToSupport, self.map)
        if value < 0:
            value *= -1; # bug: what the hell!??
        return value
    
    def getBestOutOfTheWayOrder(self, unit, orderList):
        # returns the best move unit can do not into anywhere there is an
        # order with that target
        # check to make sure this isn't null!
        validOrders = self.tactics.getValidOrders(unit)
        possibleOrders = []
        for validOrder in validOrders:
            # for each validOrder
            possible = True; # say it's possible...
            for inList in orderList:  # now for each order we're doing
                if (isinstance(validOrder, ConvoyedOrder)
                        or validOrder.destination == inList.destination
                        or (target(validOrder).units
                            and target(validOrder).unit.nation == self.map.us)):
                    # the validOrder wasn't possible as an outOfTheWay order
                    possible = False
            if possible: # if it was possible add it to possibleOrders
                possibleOrders.append(validOrder)
        if not possibleOrders:
            return None
        possibleOrders.sort(self.tactics.compareTo)
        return possibleOrders[0]
    
    def getOrderFor(self, unit, orderList):
        # post: gets the Order for unit in orderList
        for order in orderList:
            if order.unit == unit:
                return order
        return None; # should never happen!
    
    def changeOrder(self, unit, order, orderList):
        # post: changes the order of Unit unit to Order order in orderList and
        # returns the new list
        # first it removes the old order for that unit from the list - use
        # getOrderFor
        # then it inserts (ordered) the new order into the list
        orderList = [orderInList for orderInList in orderList
            if unit != orderInList.unit]
        orderList.append(order); # this is a dumb way of doing this
        orderList.sort(self.tactics.compareTo)
        order.unit.order = order
        return orderList
    
    def getUnitsAvaliable(self, orderList, i):
        # post: returns the units in orderList after i which aren't already
        # helping someone
        avaliableToHelp = []
        for order in orderList[i+1:]:
            if (not order.helping or order.helping == orderList[i]):
                # if this Order is below order and isn't helping someone
                # already, or is helping this order
                avaliableToHelp.append(order.unit)
        return avaliableToHelp
    
    def getUnitsAlsoAvaliable(self, orderList, i):
        # post: returns the units in orderList before i which are currently
        # holding
        alsoAvaliable = []
        for order in orderList[:i]:
            if isinstance(order, HoldOrder):
                alsoAvaliable.append(order.unit)
        return alsoAvaliable
    
    def Support(self, unit, order):
        if order.is_moving():
            result = SupportMoveOrder(unit, order.unit, order.destination)
        else: result = SupportHoldOrder(unit, order.unit)
        result.orderToSupport = order
        return result

class Constants(object):
    #********************** weightings and constants *************************#
    numberIterations = 10
    
    # NB All these constants are set to 1 for ease of debugging
    '''
    spring_attack_weight = 1
    # Importance of defending our own centres in Spring
    spring_defence_weight = 1
    
    # Same for autumn.
    autumn_attack_weight = 1
    autumn_defence_weight = 1
    
    # Importance of basicValue[0..n] in Spring
    spring_iteration_weight = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    
    # Importance of our attack strength on a province in Spring
    spring_strength_weight = 1
    
    # Importance of lack of competition for the province in Spring
    spring_competition_weight = 1
    
    # Importance of basicValue[0..n] in autumn
    autumn_iteration_weight = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    
    # Importance of our attack strength on a province in autumn
    autumn_strength_weight = 1
    
    # Importance of lack of competition for the province in autumn
    autumn_competition_weight = 1
    
    # Importance of building in provinces we need to defend
    build_defence_weight = 1
    
    # Importance of basicValue[0..n] when building
    build_iteration_weight = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    # Importance of removing in provinces we don't need to defend
    remove_defence_weight = 1
    
    # Importance of basicValue[0..n] when removing
    remove_iteration_weight = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    
    # Percentage change of automatically playing the best move
    play_alternative = 1
    
    # If not automatic, chance of playing best move if inferior move is nearly
    # as good
    alternative_difference_modifier = 1
    '''#'''
    
    # Importance of attacking supply centres under enemy control in Spring
    spring_attack_weight = 70
    # Importance of defending our own centres in Spring
    spring_defence_weight = 30
    
    # Same for fall.
    autumn_attack_weight = 60
    autumn_defence_weight = 40
    
    # The sum of the surrounding values is divided by this figure to work out
    # an average
    iteration_fleet_divisor = 5
    iteration_army_divisor = 5
    
    # Importance of basicValue[0..n] in Spring
    spring_iteration_weight =  [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1]
    
    # Importance of our attack strength on a province in Spring
    spring_strength_weight = 2
    
    # Importance of lack of competition for the province in Spring
    spring_competition_weight =  2
    
    autumn_iteration_weight = [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1]
    
    # Importance of our attack strength on a province in Fall
    autumn_strength_weight = 2
    
    # Importance of lack of competition for the province in Fall
    autumn_competition_weight =  2
    
    # Importance of building in provinces we need to defend
    build_defence_weight = 1000
    
    # Importance of basicValue[0..n] when building
    build_iteration_weight = [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1]
    # Importance of removing in provinces we don't need to defend
    remove_defence_weight = 1000
    
    # Importance of basicValue[0..n] when removing
    remove_iteration_weight = [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1]
    
    # Percentage change of automatically playing the best move
    play_alternative = 50
    
    # If not automatic, chance of playing best move if inferior move is nearly
    # as good
    alternative_difference_modifier = 500


# Functions that Project20M expects to be in the gameboard classes
Unit.order = None

def getStrength(power):
    # strength is:
    # A * x^2 + B * x + C
    # where A, B and C are constants
    # and x is the number of supply centres the power owns
    
    # these values are just stolen from dumbbot, they may well not be the best
    A = 1.0
    B = 4.0
    C = 16.0
    x = len(power.centers)
    return A * x * x + B * x + C

def getNumberOfAdjacentUnits(province, powerList, board):
    # returns the number of units each power in the list has which could
    # invade this province next turn
    # +1 if that power already has a unit here
    
    # surrounding units, including your ones
    surroundingUnits = getALLSurroundingUnits(province, board)
    numbers = [0 for p in powerList]
    for surroundingUnit in surroundingUnits:
        for j, power in enumerate(powerList):
            if surroundingUnit.nation == power:
                numbers[j] += 1
    return numbers

def getALLSurroundingUnits(province, board):
    # gets all the units (OURS AND ENEMIES) which could attack a unit here
    # next turn
    surroundingUnits = []
    for prov in province.borders_in:
        other = board.spaces[prov]
        surroundingUnits.extend([u for u in other.units
                if u.can_move_to(province)])
    return surroundingUnits

def getSurroundingUnits(province, board):
    # gets all the ENEMY units which could attack a unit here next turn
    surroundingUnits = []
    for prov in province.borders_in:
        other = board.spaces[prov]
        surroundingUnits.extend([u for u in other.units
                if u.can_move_to(province) and u.nation != board.us])
    return surroundingUnits

def getSurroundingPowers(province, board):
    # returns a list of the units which could enter this place/province next
    # turn
    surroundingUnits = getSurroundingUnits(province, board)
    surroundingPowers = []
    for surroundingUnit in surroundingUnits:
        thisOwner = surroundingUnit.nation
        if thisOwner not in surroundingPowers:
            # if owner isn't already in surroundingPowers
            surroundingPowers.append(thisOwner)
    return surroundingPowers

def isValuable(province, board):
    # returns true iff the province is an enemy supply centre,
    # or a threatened one of our supply centres
    if (province.is_supply() and (province.owner != board.us
            or len(getSurroundingUnits(province, board)) > 0)):
        return True;
    return False;

def strongestAdjacentOpponentStrength(province, board):
    # returns the strength of the strongest OPPONENT which has a unit which
    # could move into this province
    surroundingPowers = getSurroundingPowers(province, board)
    strongest = 0
    for surroundingPower in surroundingPowers:
        if surroundingPower != board.us:
            thisStrength = getStrength(surroundingPower)
            if thisStrength > strongest:
                strongest = thisStrength
    return strongest

def canMoveTo(unit): return unit.coast.connections

# Functions that Project20M expects to be in the order classes
UnitOrder.helping = None

def couldBeSupportedBy(order, board):
    if isinstance(order, (MoveOrder, ConvoyedOrder)):
        # Restrictions in the original, due to misunderstanding the syntax,
        # have been removed by Eric Wald on the recommendation of Andrew Huff.
        # The original project could not support convoyed armies,
        # or fleets moving to a specific coast.
        aroundTarget = getALLSurroundingUnits(target(order), board)
        while order.unit in aroundTarget:
            aroundTarget.remove(order.unit)
        return aroundTarget
    else:
        # get the list of units surrounding this one
        return getALLSurroundingUnits(order.unit.coast.province, board)

def doStrengthCompetition(order, value, board):
    # adjusts the value given, according to the strength (people who could
    # help) and competition (people who could stop us) of the order
    if getSupportsNeeded(order, board) > 1:
        value *= 2 ** target(order).strength; # strength weight = 2
    return value

def evaluate(order, board):
    if isinstance(order, BuildOrder):
        return order.unit.coast.Value

    elif isinstance(order, (DisbandOrder, RemoveOrder)):
        return -(order.unit.coast.Value)

    elif isinstance(order, MoveOrder):
        # for working out possible resistance, add in all the possible resistance
        # of the place we're moving into
        if order.unit.nation == board.us:
            if order.unit.coast == order.destination:
                # this /should/ never happen - you're moving into a place you're
                # already at
                return 0
            
            value = order.destination.Value - order.unit.coast.Value
            conflict = getResistance(order, 100, board) + 1
            
            if getSupportsNeeded(order, board) > 1:
                value *= 2 ** target(order).strength # strength weight = 2
            
            if target(order).unit: conflict += 1
            value /= conflict * conflict
            
            if target(order).unit and target(order).unit.nation == board.us:
                # the move is worth less if we already have someone there
                value /= 200
            return value
        else: return 0

    elif isinstance(order, RetreatOrder):
        return order.destination.Value - order.unit.coast.Value

    elif isinstance(order, WaiveOrder):
        return 0
    
    else:
        if order.unit.nation == board.us:
            value = 0.001 * order.unit.coast.Value
            value = doStrengthCompetition(order, value, board)
            return value
        else: return 0

def getResistance(move_order, hops, board):
    # returns the supports this move needs + the supports the unit in front
    # needs, if we are moving
    # into a place where a unit we own already is
    # hops is the max distance ahead we look
    if hops == 0: return 0
    resistance = getSupportsNeeded(move_order, board)
    if (target(move_order).unit
            and target(move_order).unit.nation == move_order.unit.nation
            and target(move_order).unit.order):
        inWay = target(move_order).unit
        if isinstance(inWay.order, MoveOrder):
            resistance += getResistance(inWay.order, hops - 1, board)
        else: resistance += getSupportsNeeded(inWay.order, board)
    return resistance

def getSupportsNeeded(order, board):
    if isinstance(order, ConvoyedOrder):
        # post: returns the number of uncuttable supports we need to be sure the
        # order will succeed
        
        # gets all the enemy units which could enter target next turn
        supportsNeeded = len(getSurroundingUnits(target(order), board))
        if target(order).unit and target(order).unit.nation != board.us:
            supportsNeeded += 1
        return supportsNeeded
    elif isinstance(order, (ConvoyingOrder, HoldOrder, SupportOrder)):
        where = order.unit.coast.province
        supportsNeeded = len(getSurroundingUnits(where, board))
        if supportsNeeded > 0:
            supportsNeeded -= 1
        return supportsNeeded
    elif isinstance(order, MoveOrder):
        # post: returns the number of uncuttable supports we need to be sure the
        # order will succeed
        
        # gets all the enemy units which could enter target next turn
        supportsNeeded = len(getSurroundingUnits(target(order), board))
        if target(order).unit and target(order).unit.nation != board.us:
            supportsNeeded += 1
        # but when it's our supply centre which is under threat
        # and there isn't an enemy unit there
        # then we don't really want to move into that place
        # just make sure nobody else moves in there
        elif target(order).owner == board.us and supportsNeeded > 0:
            supportsNeeded -= 1
        return supportsNeeded
    else: return 0

def target(order):
    if isinstance(order, (ConvoyingOrder, SupportOrder)):
        return order.supported.coast.province
    return order.destination.province


def run():
    from parlance.main import run_player
    run_player(Project20M)
