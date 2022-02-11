from flask import Flask, render_template, request
from datetime import datetime, timedelta
from hello import urlkey
import json, urllib.request, urllib.error, urllib.parse, time
#This app will call Bing maps REST services to give you some routes.  
app = Flask(__name__)
#Todo 
#  for line 30 of router.html find out how to make each new label unique 

##HELPER FUNCTIONS

#Makes json dic more legible 
def pretty(obj):
    return json.dumps(obj, sort_keys=True, indent=3)

#This funtion provides a error proof call  
def safeGet(url):
    global prompt 
    try:
        return urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        prompt = "\nThe server couldn't fulfill the request.\nError code: " + str(e.code) + " " + str(e.reason) + " (Usually nonexistant address)"
    except urllib.error.URLError as e:
         prompt = prompt + "\nWe failed to reach a server.\nReason: " + str(e.reason)
    
    return None 

def upAbook(addBook, routeCoords):
    """updates address book with the useful infomation form bingroutedata"""
    for locNum in range(len(routeCoords)):
        if locNum == 0:
            addBook[locNum]["coords"] = routeCoords[locNum]["startLocation"]["point"]["coordinates"]   
            time = addBook[locNum]["arrivalTime"]
            
        addBook[locNum+1]["coords"] = routeCoords[locNum]["endLocation"]["point"]["coordinates"]
        time += timedelta(seconds=routeCoords[locNum]["travelDuration"])
        temptime = time
        time +=  addBook[locNum+1]["arrivalTime"]
        addBook[locNum+1]["arrivalTime"] = temptime

    getWeather(addBook)

def extractData(abook, bingRouteDict):
    """Extracts data that is used from the returned from bing map data"""
    route = {
        "summary": summerize(abook, bingRouteDict['routedata']["resourceSets"][0]["resources"][0]),
        "img": bingRouteDict['routeimg'],
        "livemap": bingRouteDict['linkmap'], 
        "directions": directions(bingRouteDict['routedata']["resourceSets"][0]["resources"][0]["routeLegs"])
    }
    return route

#Cleans up RouteData to be human readable
def summerize(abook, bingRouteData):
    if  bingRouteData["travelDuration"] > 3600:
        time = str(round(bingRouteData["travelDuration"] / 3600, 2)) + " hours"
    else:
        time = str(round(bingRouteData["travelDuration"] / 60,2)) +" minutes"
        
    distance = (round(bingRouteData["travelDistance"],2))
   
    destination = abook[-1]["address"]
   
    summary = "It will take you %s miles to get too %s. Your trip should take %s."%(distance, destination, time)
    return summary

# Returns a list of directions for the route 
def directions(data):
    directionsegment = []
    for subroute in data:
        for segment in subroute["itineraryItems"]:
            directionsegment.append(segment["instruction"]["text"])
    return directionsegment

##END HELPER FUNCTIONS

##NWS API SPECIFIC FUNCTIONS
def nws_get(url):
    # make a request with the url and necessary headers
    # User-Agent: (myweatherapp.com, contact@myweatherapp.com)
    headers = {"User-Agent":"Cato's HCDE 310 final (cannizzo@uw.edu)"}
    req = urllib.request.Request(url,headers=headers) 
    # pass that request to safe_get
    result = safeGet(req)
    if result is not None: 
        return json.load(result)

def getWeather(addBook):
    """updates address book with weather info from NWS"""

    for location in addBook:
        lat = location["coords"][0]
        lng = location["coords"][1]
        weatherUrl = "https://api.weather.gov/points/{lat},{lng}".format(lat=lat,
        lng=lng)
        weatherRequest = nws_get(weatherUrl)
        if weatherRequest is not None: 
            nwsData = nws_get(weatherRequest['properties']['forecast'])
            nwsData = nwsData['properties']['periods']
            for period in nwsData:
                timeHolder = period["startTime"][:13]
                periodTime = datetime.strptime(timeHolder, '%Y-%m-%dT%H')
                if location["arrivalTime"] < periodTime:  
                    location["weather"] = period
                    break
    # Now that maths was done with arrival time we change it back to human readable to be sent to html
        location["arrivalTime"] = location["arrivalTime"].strftime("%m/%d at %H:%M")
## CLOSE NWS SPECIFIC FUNCTIONS


##BING MAPS API SPECIFIC FUNCTIONS
# https://docs.microsoft.com/en-us/bingmaps/rest-services/locations/

def getCalc(aBook, avoid = "",routeAttributes = ""):
    """Gets route + route image + and a google maps route of addresses"""
    # to make returned JSON more managable change to 'routeSummariesOnly' at 'ra' 
        # Initializing vars
    addStr = ""
    googleStr = ""
        # Initializing base urls
    baseurl = "http://dev.virtualearth.net/REST/v1/Routes/Driving?"
    imgurl = "https://dev.virtualearth.net/REST/v1/Imagery/Map/Road/Routes?"
    googleurl = "https://www.google.com/maps/dir/"

        #making url paramater strings
    for locNum in range(len(aBook)):
        addStr += "wp." + str(locNum+1) + "=" + aBook[locNum]["address"].replace(" ","+") + "&"
        googleStr += aBook[locNum]["address"].replace(" ","+") + "/"

    routeparams = addStr + urllib.parse.urlencode({'avoid':avoid,'ra':routeAttributes,'du':"mi",'key':urlkey})
    imgparams = addStr + urllib.parse.urlencode({'ms':'500,500','avoid':avoid,'ra':routeAttributes,'du':"mi",'key':urlkey})  

        # Combining urls
    routeRequest = baseurl + routeparams
    imgRequest = imgurl + imgparams
    liveMap = googleurl + googleStr
        # Requesting data
    bingData = safeGet(routeRequest)
        #Packaging all comutations into one dict 
    if bingData is not None:
        routeDict = {
            'routedata' : json.loads(bingData.read()),
            'routeimg' : imgRequest,
            'linkmap' : liveMap,
        }
        return routeDict

##END BING MAPS API FUNCTIONS
  
## ROUTE
@app.route("/", methods=['GET','POST'])
def main_handler():
    global prompt 
    prompt ="" 
    if request.method == 'POST':
        start = request.form.get('start')
        destination = request.form.get('destination')
        deTime = datetime.strptime((request.form.get('deDa')+'-'+request.form.get('deTi')), '%Y-%m-%d-%H:%M')
 
 # Checks incoming address for minimum requirement then sets up address book
        if start != "" and destination != "":
            addBook= [{"address":start,'arrivalTime':deTime}]
            for x in range(11):
                stop = request.form.get('add'+str(x),'')
                if stop:
                    stopTime =  timedelta(hours=request.form.get('time'+str(x),4,type=int))
                    addBook.append({"address":stop,'arrivalTime':stopTime})
            addBook.append({"address":destination, 'arrivalTime':timedelta(hours=0)})
            
            bingRouteDict = getCalc(addBook)
            if bingRouteDict is not None: 
                upAbook(addBook, bingRouteDict['routedata']["resourceSets"][0]["resources"][0]["routeLegs"])
                routeSummaryDict = extractData(addBook, bingRouteDict)
  
                return render_template('routemade.html', route = routeSummaryDict, locs = addBook)
        else:
            prompt = prompt + "\nPlease add starting and ending locations."
    return render_template('index.html', prompt = prompt.split('\n'))

if __name__ == "__main__":
    # Used when running locally only. 
	# When deploying to Google AppEngine, a webserver process will
	# serve your app. 
    app.run(host="localhost", port=8080, debug=True)

##UNUSED CODE

# #Checks address data to determine match quality
# def bingAddressCheck(aBook):
#     #check confidnence
#     rtnstring = "Confidence in user address %s" %(bingAddyData["resourceSets"][0]["resources"][0]["confidence"])
#     #check MatchCode
#     if bingAddyData["resourceSets"][0]["resources"][0]["matchCodes"][0] == "UpHierarchy":
#         rtnstring = rtnstring + "\nMatch quailty in bing database is poor"
#         return rtnstring
#     else:
#          rtnstring = rtnstring + "\nMatch quailty in bing database is %s" %(bingAddyData["resourceSets"][0]["resources"][0]["matchCodes"][0])
#          return rtnstring


