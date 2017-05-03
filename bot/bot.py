#!/usr/bin/python3
# coding: utf-8

import os
import config
import recastai
import requests
import random
import json
import time
import re

from flask import jsonify

# API call to get weather info and reply string formating
def checkWeather( location, date ):
    weatherInfo = [0] * 4

    # get given date if there is any and call weather API with it
    if date[0]:
        wantedDate = round(((date[1] - date[3]) / (24 * 3600)) + 1)
    if date[1]:
        ret = requests.get("http://api.openweathermap.org/data/2.5/forecast/daily?lat=" + location[1] + "&lon=" + location[2] + "&cnt=" + str(wantedDate) + "&appid=d0f270ad6a7e585555002cb9f15ca6ce")

    else:
        ret = requests.get("http://api.openweathermap.org/data/2.5/weather?lat=" + location[1] + "&lon=" + location[2] + "&appid=d0f270ad6a7e585555002cb9f15ca6ce")

    # select info from the Json the weather API has given
    jsonObj = ret.json()["list"][int(wantedDate) - 1] if date[1] else ret.json()
    temp = jsonObj["temp"]["day"] if date[1] else jsonObj["main"]["temp"]
    skyClearance = jsonObj["weather"]
    weatherInfo[3] = re.match(r'\d{2}', skyClearance[0]["icon"]).group()

    # format reply string depending of the date wanted
    tense = "it's " if int(weatherInfo[3]) == 1 else "there are " if int(weatherInfo[3]) <= 4 else "there is "
    tense = "it will be " if int(weatherInfo[3]) == 1 and date[1] else "there will be " if date[1] else tense
    weatherInfo[0] =  "It will be " if date[1] else "It's "
    weatherInfo[0] += str(round(float(temp) - 273.15, 1))
    weatherInfo[1] = skyClearance[0]["icon"]

    # format reply depending on the weather
    if weatherInfo[1] == "01d":
         weatherInfo[2] = tense + "a sunny day"
    elif weatherInfo[1] == "01n":
         weatherInfo[2] = tense + "a clear night"
    else:
        weatherInfo[2] = tense + skyClearance[0]["description"]

    weatherInfo[1] = round(float(temp) - 273.15, 1)

    return (weatherInfo)

# get X random numbers from a given interval
def getRandNumbers( limit, length ):
    lst = [0] * length
    i = 0
    nb = -1

    while i < length:
        nb = random.randint(0, limit)
        j = 0
        while j < i and lst[j]:
            while lst[j] == nb:
                nb = random.randint(0, limit)
            j += 1
        lst[i] = nb
        i += 1

    return (lst)

# get a list of 'nbRlt' locations matching the given intent
def getLocationList( intent, location, googleKey, nbRlt, bln ):
    #bln == 1 means that the previous API call hasn't sent enough locations, so we make another call to the API with bigger radius
    if bln == 1:
        ret = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=" + location[1] + "," + location[2] + "&radius=2500&type=" + intent + "&key=" + googleKey)
    else:
        formatedQuery = location[0] + "+in+" + intent
        ret = requests.get("https://maps.googleapis.com/maps/api/place/textsearch/json?query=" + formatedQuery + "&language=en&key=" + googleKey)

    googleJson = ret.json()

    # make sure not to ask for too many results, not to ask for 3 museum in a place with only 2
    nbLoc = len(googleJson["results"])
    wantedLength = nbLoc if int(nbLoc) < int(nbRlt) else nbRlt
    randNo = getRandNumbers( nbLoc - 1, wantedLength )

    # get the locations name from googleJson
    i = 0
    lst = [0] * wantedLength
    while i < wantedLength:
        lst[i] = googleJson["results"][randNo[i]]["name"]
        i += 1

    # recursive call to the function if there is less than 5 locations found but only once
    if bln == 0 and nbLoc < 5:
        lst = getLocationList( intent, location, googleKey, nbRlt, 1 )

    return lst

# check if there is any better option depending on time, weather and day of the week and if it's the case add an extra answer
def offerAlternatives( slug, date, location, googleKey ):
    weatherData = checkWeather( location, date )
    currentTime = int(time.strftime("%H", date[4]))
    reply = ""

    # check if there is no better option depending on the weather
    if date[0] or (date[0] == None and currentTime > 9 and currentTime <= 19):

        # check if it won't be better to go to a park
        if slug == "museum" and int(weatherData[3]) < 4 and weatherData[1] >= 15:
            verb = "it will be " if date[0] else "it's "
            wantedDay = " on " + date[0] if date[0] else ""
            extraChoice = getLocationList( 'park', location, googleKey, 1, 2 )
            if extraChoice and extraChoice[0]:
                reply += "And, well, since " + verb + "nice out there" + wantedDay + ", you may want to go to a park instead, maybe '" + extraChoice[0] + "'?"

        # check if it won't be better to go to a museum
        if slug == "park" and int(weatherData[3]) > 3 and weatherData[1] < 12:
            verb = "it won't be " if date[0] else "it's not "
            nice = "nice" if int(weatherData[3]) > 3 else "warm"
            wantedDay = " on " + date[0] if date[0] else ""
            extraChoice = getLocationList( "museum", location, googleKey, 1, 2 )[0]
            if extraChoice:
                reply += "And, well, since " + verb + "so " + nice + " out there" + wantedDay + ", you may want to go to a museum instead, maybe '" + extraChoice + "'?"

    # check if the time and day matches supposed opening hours
    if slug == "museum" and time.strftime("%a", date[4]) == "Sun":
        reply += "\nBut since it's sunday, it might be close and you should want to go somewhere else."
    elif currentTime >= 20:
        reply += "\nBut since it's past 8pm, it might be close and you should want to go somewhere else."
    elif currentTime < 9:
        reply += "\nBut since it's not 9am yet, it might be close and you should want to go somewhere else."

    return (reply)

# get the reply for the 'park' or 'museum' intent
def DemandReply ( slug, location, date, googleKey ):

    locationLst = getLocationList( slug, location, googleKey, 3, 0 )
    tblLocLen = len(locationLst)

    if tblLocLen == 0:
        reply =  "I'm sorry, I cannot find any " + slug + " in " + location[0] + "."
        reply += "\n" + "It doesn't necessarily mean there isn't any, maybe the API isn't responding."

    elif locationLst[0]:
        reply = "You can visit '" if slug == "museum" else "You can go to '"
        reply += locationLst[0] + "' "
        if tblLocLen > 1:
            reply += "or '" + locationLst[1] + "' "
        if tblLocLen > 2:
            reply += "or else '" + locationLst[2] + "' "
        reply += "in " + location[0] + ". "
        reply += offerAlternatives( slug, date, location, googleKey )

    return (reply)

# format the reply string
def getReply ( dataResponse, response, client, message, date, location, googleKey ):
    reply = None

    # if there are no intent and no location : reset memory
    if not response.intent and not response.entities:
        reply = "I haven't understood you, can you specify your request? I can give you the weather or some indications to go to a park or a museum."
        dataResponse.reset_memory()

    else:
        # pick info (intent or location) from memory if one of them is missing
        slug = response.intent.slug if response.intent and response.intent.slug else dataResponse.get_memory("intent").slug if dataResponse.get_memory("intent") else None

        if slug:
            if slug == "greeting":
                reply = client.request.converse_text(message).replies[0]

            # check if the intent matches one that the bot handles and gather all the needed info
            if slug == "parks" or slug == "museum" or slug == "get-weather":

                # google API request with 'parks' returns all the car parks so the slug has to be 'park' and not 'parks'
                slug = "park" if slug == "parks" else slug

                # get location from memory if none is given
                if not location[0]:
                    if dataResponse.get_memory("location"):
                        location[0] = dataResponse.get_memory("location").raw
                    else:
                        slugResponse = "the weather in any city" if slug == "get-weather" else "any " + slug + " you can go to"
                        return ("I really need a location to give you " + slugResponse + ", please ask me again with a location!")

                if slug == "get-weather":
                    weatherLst = checkWeather( location, date )
                    reply = weatherLst[0] + "C and " + weatherLst[2] + " in " + location[0]
                    if date[0]:
                        return (reply + " on " + time.strftime("%A %B %-d, %Y", date[2]))

                # get reply for 'park' or 'museum' intent
                elif location[0]:
                    reply = DemandReply ( slug, location, date, googleKey )

        # send reply if there is no matching intent
        elif location[0]:
            reply = "What do you want to know about " + location[0] + "?"

    return (reply)

# get all the info needed for each entity to be processed
def setEntities( date, location, response, dataResponse, recastJson, googleKey ):

    date[3] = time.time()

    # check if there is already a location in memory
    if dataResponse.get_memory("location"):
        location[0] = dataResponse.get_memory("location").raw
        location[1] = str(round(dataResponse.get_memory("location").lat, 2))
        location[2] = str(round(dataResponse.get_memory("location").lng, 2))

    for entity in recastJson["results"]["entities"]:
        if entity == "datetime":
            regex = re.match(r'^(.*)[+|-]', recastJson["results"]["entities"]["datetime"][0]["iso"]).group(1).replace("-", "")
            date[0] = recastJson["results"]["entities"]["datetime"][0]["raw"]
            date[1] = time.mktime(time.strptime(regex, "%Y%m%dT%H:%M:%S"))
        if entity == "location":
            dataResponse.set_memory({'location':recastJson["results"]["entities"]["location"][0]})
            location[0] = recastJson["results"]["entities"]["location"][0]["raw"]
            location[1] = str(round(recastJson["results"]["entities"]["location"][0]["lat"], 2))
            location[2] = str(round(recastJson["results"]["entities"]["location"][0]["lng"], 2))

    # get time for the specified location
    if location[0]:
        if date[0]:
            timeJson = requests.get("https://maps.googleapis.com/maps/api/timezone/json?location=" + location[1] + "," + location[2] + "&timestamp=" + str(date[1]) + "&key=" + googleKey).json()
            date[1] = date[1] + timeJson["rawOffset"] +timeJson["dstOffset"]
        timeJson = requests.get("https://maps.googleapis.com/maps/api/timezone/json?location=" + location[1] + "," + location[2] + "&timestamp=" + str(date[3]) + "&key=" + googleKey).json()
        date[3] = date[3] + timeJson["rawOffset"] +timeJson["dstOffset"]

    # get time tuple from epoch
    if date[1]:
        date[2] = time.gmtime(date[1])
    date[4] = time.gmtime(date[3])

    return

# replace common symbols that aren't displayed propely
def noAccentReply( reply ):

    for letter in reply:

        if letter == 'á' or letter == 'à' or letter == 'â' or letter == 'ä' or letter == 'ã' or letter == 'å':
            reply = reply.replace(letter, 'a')
        if letter == 'ó' or letter == 'ò' or letter == 'ô' or letter == 'ö' or letter == 'õ':
            reply = reply.replace(letter, 'o')
        if letter == 'é' or letter == 'è' or letter == 'ê' or letter == 'ë':
            reply = reply.replace(letter, 'e')
        if letter == 'ú' or letter == 'ù' or letter == 'û' or letter == 'ü':
            reply = reply.replace(letter, 'u')
        if letter == 'í' or letter == 'ì' or letter == 'î' or letter == 'ï':
            reply = reply.replace(letter, 'i')
        if letter == 'ç':
            reply = reply.replace(letter, 'c')

        if letter == 'Á' or letter == 'À' or letter == 'Â' or letter == 'Ä' or letter == 'Ã' or letter == 'Å':
            reply = reply.replace(letter, 'A')
        if letter == 'Ó' or letter == 'Ò' or letter == 'Ô' or letter == 'Ö' or letter == 'Ö':
            reply = reply.replace(letter, 'O')
        if letter == 'É' or letter == 'È' or letter == 'Ê' or letter == 'Ë':
            reply = reply.replace(letter, 'E')
        if letter == 'Ú' or letter == 'Ù' or letter == 'Û' or letter == 'Ü':
            reply = reply.replace(letter, 'U')
        if letter == 'Í' or letter == 'Ì' or letter == 'Î' or letter == 'Ï':
            reply = reply.replace(letter, 'I')
        if letter == 'Ç':
            reply = reply.replace(letter, 'C')

    return reply

def bot( payload ):

    # get info from RecastAI API
    client = recastai.Client(token=os.environ['REQUEST_TOKEN'])
    connect = recastai.Connect(token=os.environ['REQUEST_TOKEN'], language=os.environ['LANGUAGE'])
    request = recastai.Request(token=os.environ['REQUEST_TOKEN'])
    data = connect.parse_message(payload)
    message = data.content
    dataResponse = request.converse_text(message, conversation_token=data.sender_id)
    response = request.analyse_text(message)

    googleKey = "AIzaSyAQN2eZ0HtgkVMTFBNlPn7hMKnAQQsw5co"

    recastJson = json.loads(response.raw)

    # set the bot memory if any element matches the one it keeps in memory
    if response.intent and response.intent.slug and float(response.intent.confidence) >= 0.7:
        dataResponse.set_memory({'intent':recastJson["results"]["intents"][0]})

    # initialization of the time and location tuples
    date = [None] * 5
    location = [None] * 3
    setEntities( date, location, response, dataResponse, recastJson, googleKey )

    reply = noAccentReply ( getReply( dataResponse, response, client, message, date, location, googleKey ))

    replies = [{'type': 'text', 'content': reply}]
    connect.send_message(replies, data.conversation_id)

    return jsonify(status=200)
