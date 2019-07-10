# Import necessary libraries
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, func
from flask_sqlalchemy import SQLAlchemy

from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect)


#################################################
# Flask Setup
#################################################
app = Flask(__name__)

#################################################
# Database Setup
#################################################
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '') or "sqlite:///airbnb_crime_dataset.sqlite"
db = SQLAlchemy(app)

# reflect an existing database into a new model
Base = automap_base()
# reflect the tables
Base.prepare(db.engine, reflect=True)

Crime = Base.classes.crime
Listings = Base.classes.listings
Reviews = Base.classes.reviews
#################################################
# Create a route that renders index.html template
#################################################
@app.route("/")
def home():
    return render_template("index.html")


#########################################################################
# create a route for network Vosualization (Mona Arami)
#########################################################################
@app.route("/api/network_viz")
def network():

    result_crime = db.session.query(Crime.OFFENSE_CATEGORY_ID,Crime.NEIGHBORHOOD_ID).all()
    result_listings = db.session.query(Listings.price,Listings.neighbourhood).all()

    # create lists to be turned into database
    OFFENSE_CATEGORY_ID = []
    NEIGHBORHOOD_ID = []
    Listings_Price = []
    Listings_Neighbourhood = []

    # loop thru results and append to list
    for row in result_crime:
        OFFENSE_CATEGORY_ID.append(row[0])
        NEIGHBORHOOD_ID.append(row[1])

    crime_df = pd.DataFrame({
       "neighborhood": NEIGHBORHOOD_ID,
       "total_crime": OFFENSE_CATEGORY_ID,
    })

    for row in result_listings:
        Listings_Price.append(row[0])
        Listings_Neighbourhood.append(row[1])

    listing_df = pd.DataFrame({
        "neighborhood": Listings_Neighbourhood,
        "average_price": Listings_Price,
    })
    #fixing columns
    crime_df['neighborhood'] = crime_df['neighborhood'].str.replace("-"," ")
    count_crime = crime_df.groupby(['neighborhood']).count()
    count_crime['total_crime'] = count_crime['total_crime'].astype(np.float64)

    final_crime_count = count_crime.reset_index()
    
    #converting currency with $ and , to numbers
    # group listing_df by neighborhood_listing 
    listing_df["average_price"] = listing_df["average_price"].str.replace("[\$,]","")
    listing_df['average_price'] = listing_df['average_price'].astype(np.float64)
    listing_df['neighborhood'] = listing_df['neighborhood'].str.lower()

    average_price = listing_df.groupby(['neighborhood']).mean().round(2)
  
    final_average_price = average_price.reset_index()

    merge_df = pd.merge(final_average_price, final_crime_count, on="neighborhood", how="inner")

    final_dict = merge_df.to_dict(orient='records')

    return jsonify(final_dict)
#########################################################################
# create a route - load neighbourhoods.geojson
#########################################################################
@app.route("/api/geojson")
def geo():
    filename = os.path.join(app.static_folder, 'neighbourhoods.geojson')
    with open(filename) as blog_file:
        data = json.load(blog_file)
    return jsonify(data)
    
#########################################################################
# create json file from listing table
#########################################################################

@app.route("/api/geojson/listings")
def listing_geojson():
    sel = [Listings.latitude, Listings.longitude, Listings.neighbourhood, Listings.property_type, Listings.room_type, Listings.price, Listings.number_of_reviews, Listings.review_scores_rating]

    results = db.session.query(*sel).all()

    mylist = []

    for result in results:
        listings_map = {}
        listings_map["type"] = "Feature"
        listings_map["geometry"] = {}
        listings_map["geometry"]["type"] = "Point"
        listings_map["geometry"]["coordinates"] = [result[0], result[1]]
        listings_map["properties"] = {}
        listings_map["properties"]["neighborhood"] = result[2]
        listings_map["properties"]["property_type"] = result[3]
        listings_map["properties"]["room_type"] = result[4]
        listings_map["properties"]["price"] = result[5]
        listings_map["properties"]["number_of_reviews"] = result[6]
        listings_map["properties"]["review_scores_rating"] = result[7]
        mylist.append(listings_map)

   
    listing_geojson = {"type": "FeatureCollection", "features": mylist }
    
    return jsonify(listing_geojson)
########################################################################
# create json file from crime table
#########################################################################

@app.route("/api/geojson/crime")
def crime_geojson():
    sel = [Crime.GEO_LAT, Crime.GEO_LON, Crime.NEIGHBORHOOD_ID]
    results = db.session.query(*sel).all()

    mylist_crime = []

    for result in results:
        crime_map = {}
        crime_map["type"] = "Feature"
        crime_map["geometry"] = {}
        crime_map["geometry"]["type"] = "Point"
        crime_map["geometry"]["coordinates"] = [result[0], result[1]]
        crime_map["properties"] = {}
        crime_map["properties"]["neighborhood"] = result[2]
        mylist_crime.append(crime_map)
        
    crime_geojson = {"type": "FeatureCollection", "features": mylist_crime }
    
    return jsonify(crime_geojson)

#################################################
# create a route that outputs unique neighborhood names
#################################################
@app.route("/api/neighborhoodnames")
def getNeighborhoodNames():

    # Use Pandas to perform the sql query to obtain the unique neighborhood names
    stmt = db.session.query(Listings).statement
    df = pd.read_sql_query(stmt, db.session.bind)
    df = df[df['neighbourhood']!="NaN"]
    neighborhoodList = list(df['neighbourhood'].unique())

    # Return a list of the unique country names
    return jsonify(neighborhoodList)
    
#########################################################################
# create a route -  pie
#########################################################################
@app.route("/api/pie/<selectedneighborhood>")
def piechartdata(selectedneighborhood):
    # Use Pandas to perform the sql query to obtain the unique Neighborhood names
    stmt = db.session.query(Listings).statement
    df = pd.read_sql_query(stmt, db.session.bind)
    df = df[df['neighbourhood']!="NaN"]
    df = df[df['property_type']!="NaN"]
    df = df.groupby(['neighbourhood', 'property_type'])['id'].count().reset_index(level='property_type')
    df.columns = ['property_type','count']
    df = df.loc[selectedneighborhood]
    room_type_json = df.to_json(orient='records')
   
    return room_type_json

#########################################################################
# create a route that outputs review count by year for selected neighborhood
#########################################################################
@app.route("/api/<selectedneighborhood>")
def dataForPlotlyPlot(selectedneighborhood):

    # Use Pandas to perform the sql query to obtain the unique neighborhood names
    result_reviews = db.session.query(Reviews.listing_id, Reviews.date).all()
    result_listings = db.session.query(Listings.id,Listings.neighbourhood).all()
    listing_id = []
    date = []
    id = []
    neighbourhood = []

    # loop thru results and append to list
    for row in result_reviews:
        listing_id.append(row[0])
        date.append(row[1])

    review_df = pd.DataFrame({
       "id": listing_id,
       "date": date,
    })

    for row in result_listings:
        id.append(row[0])
        neighbourhood.append(row[1])

    listing_df = pd.DataFrame({
        "id": id,
        "neighborhood": neighbourhood,
    })
    
    df = pd.merge(review_df,listing_df, on="id", how="inner")
    df = df[df['neighborhood']!="NaN"]
    df = df[df['date']!="NaN"]
    df['date'] = df['date'].apply(lambda x: datetime.strptime(x, "%m/%d/%y"))
    df['year'] = df['date'].dt.year
    df = df.groupby(['neighborhood', 'year'])['id'].count().reset_index(level='year')
    df.columns= ['year','count']
    df = df.loc[selectedneighborhood]
    json_for_plotly = df.to_json(orient='records')

    # Return a list of the unique Neighborhood names
    return json_for_plotly



if __name__ == "__main__":
    app.run()