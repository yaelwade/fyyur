#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

import sys
import json
import dateutil.parser
import babel
from flask import Flask, render_template, request, Response, flash, redirect, url_for, jsonify, abort
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
from flask_wtf import Form
from forms import *
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.sql import func

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db = SQLAlchemy(app)

migrate = Migrate(app, db)

#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#

class Availability(db.Model):
    __tablename__ = 'availabilities'

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey('artists.id'), nullable=False)
    start_time = db.Column(db.Time(timezone=True))
    end_time = db.Column(db.Time(timezone=True))

class Show(db.Model):
    __tablename__ = 'shows'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venues.id'), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artists.id'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True))

class Venue(db.Model):
    __tablename__ = 'venues'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    genres = db.Column(db.String(120))
    address = db.Column(db.String(120))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    phone = db.Column(db.String(120))
    website = db.Column(db.String(120))
    facebook_link = db.Column(db.String(120))
    seeking_talent = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String)
    image_link = db.Column(db.String(500))
    venue_shows = db.relationship('Show', backref='venue', lazy=True)
    artists = db.relationship('Artist', secondary='shows', backref='venue')
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f'{self.name}'

class Artist(db.Model):
    __tablename__ = 'artists'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    genres = db.Column(db.String(120))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    phone = db.Column(db.String(120))
    website = db.Column(db.String(120))
    facebook_link = db.Column(db.String(120))
    seeking_venue = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String)
    image_link = db.Column(db.String(500))
    artist_shows = db.relationship('Show', backref='artist', lazy=True)
    venues = db.relationship( 'Venue', secondary='shows', backref='artist')
    artist_availability = db.relationship('Availability', backref='artist', lazy=True)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f'{self.name}'

#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#

def format_datetime(value, format='medium'):
  date = dateutil.parser.parse(value)
  if format == 'full':
      format = "EEEE MMMM, d, y 'at' h:mma"
  elif format == 'medium':
      format = "EE MM, dd, y h:mma"
  return babel.dates.format_datetime(date, format, locale='en')

app.jinja_env.filters['datetime'] = format_datetime

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
  venues = Venue.query.order_by(desc(Venue.date_created)).limit(10).all()
  artists = Artist.query.order_by(desc(Artist.date_created)).limit(10).all()
  return render_template('pages/home.html', venues=venues, artists=artists)

#  Venues
#  ----------------------------------------------------------------

@app.route('/venues')
def venues():
  # Reference https://stackoverflow.com/questions/21301934/how-to-compare-dates-in-sqlalchemy
  # Reference https://hackersandslackers.com/database-queries-sqlalchemy-orm/
  # Get areas from Venue data
  all_areas = []
  areas = db.session.query(Venue.city, Venue.state).group_by(Venue.city, Venue.state).all()
  for area in areas:
      all_venues = []
      venues = Venue.query.filter_by(state=area.state).filter_by(city=area.city).all()
      for venue in venues:
          # Get upcoming shows by venue_id and ensure start time is after current date/time
          upcoming_shows = Show.query.filter(Show.venue_id == venue.id).filter(Show.start_time > datetime.now()).all()
          all_venues.append({
              'id': venue.id,
              'name': venue.name,
          })
      # Add matching venues to list "all_areas"
      all_areas.append({
          'city': area.city,
          'state': area.state,
          'venues': all_venues
      })
  return render_template('pages/venues.html', areas=all_areas)

@app.route('/venues/search', methods=['POST'])
def search_venues():
  # Get search data
  search_term = request.form['search_term']
  # Get venues with name/city/state that contains search data
  venues = Venue.query.filter(Venue.name.contains(search_term)).all()
  venues_by_city = Venue.query.filter(Venue.city.contains(search_term)).all()
  venues_by_state = Venue.query.filter(Venue.state.contains(search_term)).all()
  venues += venues_by_city
  venues += venues_by_state
  all_venues = []
  for venue in venues:
      upcoming_shows = db.session.query(Show).filter(Show.venue_id == venue.id).filter(Show.start_time > datetime.now()).all()
      all_venues.append({
          'id': venue.id,
          'name': venue.name,
      })
  results = {
      'venues': all_venues,
      'count': len(venues)
  }
  return render_template('pages/search_venues.html', results=results, search_term=request.form.get('search_term'))

@app.route('/venues/<venue_id>')
def show_venue(venue_id):
  venue = Venue.query.filter(Venue.id == venue_id).first()
  upcoming_shows = Show.query.filter(Show.venue_id == venue_id).filter(Show.start_time > datetime.now()).all()
  # Populate "all_upcoming_shows" with venues that start after now
  if len(upcoming_shows) > 0:
      all_upcoming_shows = []
      for upcoming_show in upcoming_shows:
          artist = Artist.query.filter(Artist.id == upcoming_show.artist_id).first()
          all_upcoming_shows.append({
              'artist_id': artist.id,
              'artist_name': artist.name,
              'artist_image_link': artist.image_link,
              'start_time': str(upcoming_show.start_time),
          })
      venue.upcoming_shows = all_upcoming_shows
      venue.upcoming_shows_count = len(all_upcoming_shows)
  past_shows = Show.query.filter(Show.venue_id == venue_id).filter(Show.start_time < datetime.now()).all()
  # Populate "all_past_shows" with venues that start before now
  if len(past_shows) > 0:
      all_past_shows = []
      for past_show in past_shows:
          artist = Artist.query.filter(Artist.id == past_show.artist_id).first()
          all_past_shows.append({
              'artist_id': artist.id,
              'artist_name': artist.name,
              'artist_image_link': artist.image_link,
              'start_time': str(past_show.start_time),
          })
      venue.past_shows = all_past_shows
      venue.past_shows_count = len(all_past_shows)
  return render_template('pages/show_venue.html', venue=venue)

#  Create Venue
#  ----------------------------------------------------------------

@app.route('/venues/create', methods=['GET'])
def create_venue_form():
  form = VenueForm()
  return render_template('forms/new_venue.html', form=form)

@app.route('/venues/create', methods=['POST'])
def create_venue_submission():
  error = False
  name = request.form.get('name')
  genres = request.form.get('genres')
  address = request.form.get('address')
  city = request.form.get('city')
  state = request.form.get('state')
  phone = request.form.get('phone')
  website = request.form.get('website')
  facebook_link = request.form.get('facebook_link')
  seeking_talent = request.form.get('seeking_talent')
  if seeking_talent is None:
      st = False
  if seeking_talent is 'y':
      st = True
  seeking_description = request.form['seeking_description']
  image_link = request.form['image_link']
  try:
    venue = Venue(
        name=name,
        genres=genres,
        address=address,
        city=city,
        state=state,
        phone=phone,
        website=website,
        facebook_link=facebook_link,
        seeking_talent=st,
        seeking_description=seeking_description,
        image_link=image_link,
    )
    db.session.add(venue)
    db.session.commit()
  except:
    error = True
    db.session.rollback()
  finally:
    db.session.close()
  if error:
    flash('An error occured. Venue ' + name + ' could not be listed.')
  else:
    flash('Venue ' + request.form['name'] + ' was successfully listed!')
  return redirect(url_for('index'))

@app.route('/venues/<venue_id>/delete', methods=['DELETE'])
def delete_venue(venue_id):
  error = False
  try:
    venue = Venue.query.get(venue_id)
    db.session.delete(venue)
    db.session.commit()
  except:
    db.session.rollback()
    error = True
  finally:
    db.session.close()
  if error:
    flash('An error occured. Venue ' + venue.name + ' could not be deleted.')
    abort(500)
  else:
    flash('Venue ' + venue.name + ' was successfully deleted!')
  return jsonify({'success': True})

#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
  data = Artist.query.all()
  return render_template('pages/artists.html', artists=data)

@app.route('/artists/search', methods=['POST'])
def search_artists():
  # Prepare search data
  search_term = request.form['search_term']
  artists = Artist.query.filter(Artist.name.contains(search_term)).all()
  artists_by_city = Artist.query.filter(Artist.city.contains(search_term)).all()
  artists_by_state = Artist.query.filter(Artist.state.contains(search_term)).all()
  artists += artists_by_city
  artists += artists_by_state
  all_artists = []
  for artist in artists:
      upcoming_shows = db.session.query(Show).filter(Show.artist_id == artist.id).filter(Show.start_time > datetime.now()).all()
      all_artists.append({
          'id': artist.id,
          'name': artist.name,
      })
  results = {
      'artist': all_artists,
      'count': len(artists)
  }
  return render_template('pages/search_artists.html', results=results, search_term=request.form.get('search_term', ''))

@app.route('/artists/<artist_id>')
def show_artist(artist_id):
  artist = Artist.query.filter(Artist.id == artist_id).first()
  upcoming_shows = Show.query.filter(Show.artist_id == artist_id).filter(Show.start_time > datetime.now()).all()
  availabilities = Availability.query.filter(Availability.artist_id == artist_id).all()
  # Populate "all_upcoming_shows" with venues that start after now
  if len(upcoming_shows) > 0:
      all_upcoming_shows = []
      for upcoming_show in upcoming_shows:
          venue = Venue.query.filter(Venue.id == upcoming_show.venue_id).first()
          all_upcoming_shows.append({
              'venue_id': venue.id,
              'venue_name': venue.name,
              'venue_image_link': venue.image_link,
              'start_time': str(upcoming_show.start_time),
          })
      artist.upcoming_shows = all_upcoming_shows
      artist.upcoming_shows_count = len(all_upcoming_shows)
  past_shows = Show.query.filter(Show.artist_id == artist_id).filter(Show.start_time < datetime.now()).all()
  # Populate "all_past_shows" with venues that start before now
  if len(past_shows) > 0:
      all_past_shows = []
      for past_show in past_shows:
          venue = Venue.query.filter(Venue.id == past_show.venue_id).first()
          all_past_shows.append({
              'venue_id': venue.id,
              'venue_name': venue.name,
              'venue_image_link': venue.image_link,
              'start_time': str(past_show.start_time),
          })
      artist.past_shows = all_past_shows
      artist.past_shows_count = len(all_past_shows)
  artist.availabilities = availabilities
  return render_template('pages/show_artist.html', artist=artist)

#  Update
#  ----------------------------------------------------------------
@app.route('/artists/<artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
  form = ArtistForm()
  artist = Artist.query.filter_by(id=artist_id).first()
  return render_template('forms/edit_artist.html', form=form, artist=artist)

@app.route('/artists/<artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
  error = False
  name = request.form.get('name')
  genres = request.form.get('genres')
  address = request.form.get('address')
  city = request.form.get('city')
  state = request.form.get('state')
  phone = request.form.get('phone')
  website = request.form.get('website')
  facebook_link = request.form.get('facebook_link')
  seeking_venue = request.form.get('seeking_venue')
  # Checkbox value in view evaluates to None or 'y' when unchecked or checked
  if seeking_venue is None:
      sv = False
  if seeking_venue is 'y':
      sv = True
  seeking_description = request.form['seeking_description']
  image_link = request.form['image_link']
  try:
    artist = Artist.query.get(artist_id)
    artist.name = name
    artist.genres = genres
    artist.address = address
    artist.city = city
    artist.state = state
    artist.phone = phone
    artist.website = website
    artist.facebook_link = facebook_link
    artist.seeking_venue = sv
    artist.seeking_description = seeking_description
    artist.image_link = image_link
    db.session.commit()
  except:
    error = True
    db.session.rollback()
  finally:
    db.session.close()
  if error:
    flash('An error occured. Artist ' + name + ' could not be edited.')
  else:
    flash('Artist ' + request.form['name'] + ' was successfully edited!')
  return redirect(url_for('show_artist', artist_id=artist_id))

@app.route('/venues/<venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
  form = VenueForm()
  venue = Venue.query.filter_by(id=venue_id).first()
  return render_template('forms/edit_venue.html', form=form, venue=venue)

@app.route('/venues/<venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
  error = False
  name = request.form.get('name')
  genres = request.form.get('genres')
  address = request.form.get('address')
  city = request.form.get('city')
  state = request.form.get('state')
  phone = request.form.get('phone')
  website = request.form.get('website')
  facebook_link = request.form.get('facebook_link')
  seeking_talent = request.form.get('seeking_talent')
  # Checkbox value in view evaluates to None or 'y' when unchecked or checked
  if seeking_talent is None:
      st = False
  if seeking_talent is 'y':
      st = True
  seeking_description = request.form['seeking_description']
  image_link = request.form['image_link']
  try:
    venue = Venue.query.get(venue_id)
    venue.name = name
    venue.genres = genres
    venue.address = address
    venue.city = city
    venue.state = state
    venue.phone = phone
    venue.website = website
    venue.facebook_link = facebook_link
    venue.seeking_talent = st
    venue.seeking_description = seeking_description
    venue.image_link = image_link
    db.session.commit()
  except:
    error = True
    db.session.rollback()
  finally:
    db.session.close()
  if error:
    flash('An error occured. Venue ' + name + ' could not be edited.')
  else:
    flash('Venue ' + request.form['name'] + ' was successfully edited!')
  return redirect(url_for('show_venue', venue_id=venue_id))

#  Create Availability
#  ----------------------------------------------------------------

@app.route('/artists/<artist_id>/availability', methods=['GET'])
def create_availability_form(artist_id):
  form = AvailabilityForm()
  artist = Artist.query.filter_by(id=artist_id).first()
  form.artist_id.data = artist.id
  return render_template('forms/new_availability.html', form=form, artist=artist)

@app.route('/artists/<artist_id>/availability', methods=['POST'])
def create_availability_submission(artist_id):
  error = False
  artist_id = request.form.get('artist_id')
  start_time = request.form['start_time']
  end_time = request.form['end_time']
  try:
    availability = Availability(
        artist_id=artist_id,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(availability)
    db.session.commit()
  except:
    error = True
    db.session.rollback()
  finally:
    db.session.close()
  if error:
    flash('An error occured. Availability could not be listed.')
  else:
    flash('Availability was successfully listed!')
  return redirect(url_for('index'))

#  Create Artist
#  ----------------------------------------------------------------

@app.route('/artists/create', methods=['GET'])
def create_artist_form():
  form = ArtistForm()
  return render_template('forms/new_artist.html', form=form)

@app.route('/artists/create', methods=['POST'])
def create_artist_submission():
  error = False
  name = request.form.get('name')
  genres = request.form.get('genres')
  city = request.form.get('city')
  state = request.form.get('state')
  phone = request.form.get('phone')
  website = request.form.get('website')
  facebook_link = request.form.get('facebook_link')
  seeking_venue = request.form.get('seeking_talent')
  # Checkbox value in view evaluates to None or 'y' when unchecked or checked
  if seeking_venue is None:
      sv = False
  if seeking_venue is 'y':
      sv = True
  seeking_description = request.form['seeking_description']
  image_link = request.form['image_link']
  try:
    artist = Artist(
        name=name,
        genres=genres,
        city=city,
        state=state,
        phone=phone,
        website=website,
        facebook_link=facebook_link,
        seeking_venue=sv,
        seeking_description=seeking_description,
        image_link=image_link,
    )
    db.session.add(artist)
    db.session.commit()
  except:
    error = True
    db.session.rollback()
  finally:
    db.session.close()
  if error:
    flash('An error occured. Artist ' + name + ' could not be listed.')
  else:
    flash('Artist ' + request.form['name'] + ' was successfully listed!')
  return redirect(url_for('index'))

#  Shows
#  ----------------------------------------------------------------

@app.route('/shows')
def shows():
  # Create empty list "all_shows"
  data = []
  # Get data SELECT from Venues, Artists, where venue_id and artist_id matches for given show
  shows = db.session.query(
        Venue.name,
        Artist.name,
        Artist.image_link,
        Show.start_time,
        Show.artist_id,
        Show.venue_id
      ).filter(Venue.id == Show.venue_id, Artist.id == Show.artist_id)
  print(shows)
  # Pass data to dictionary "data"
  for show in shows:
    print(show)
    data.append({
        'venue_name': show[0],
        'artist_name': show[1],
        'artist_image_link': show[2],
        'start_time': str(show[3]),
        'artist_id': show[4],
        'venue_id': show[5]
      })
  return render_template('pages/shows.html', shows=data)

@app.route('/shows/search', methods=['POST'])
def search_shows():
  # Reference https://stackoverflow.com/questions/444475/sqlalchemy-turning-a-list-of-ids-to-a-list-of-objects
  # Get search data
  search_term = request.form['search_term']
  # Get all Artists/Venues with search_term in name/city/state
  artists = Artist.query.filter(Artist.name.contains(search_term)).all()
  venues = Venue.query.filter(Venue.name.contains(search_term)).all()
  venues_by_city = Venue.query.filter(Venue.city.contains(search_term)).all()
  venues_by_state = Venue.query.filter(Venue.state.contains(search_term)).all()
  # Create empty lists
  all_shows = []
  all_artists = []
  all_venues = []
  # For each object list check if a show exists (by either artist_id or venue_id)
  # If exists add show.id to list "shows" and subsequently to list "all_artists" or "all_venues" depending
  for artist in artists:
    if Show.query.filter_by(artist_id=artist.id).first():
      all_shows += [show.id for show in Show.query.filter_by(artist_id=artist.id).all() if not show.id in all_shows]
      print(all_shows)
      for show in all_shows:
        all_artists.append(show)
  for venue in venues:
    if Show.query.filter_by(venue_id=venue.id).first():
      all_shows += [show.id for show in Show.query.filter_by(venue_id=venue.id).all() if not show.id in all_shows]
      for show in all_shows:
        all_venues.append(show)
  for venue in venues_by_city:
    if Show.query.filter_by(venue_id=venue.id).first():
      all_shows += [show.id for show in Show.query.filter_by(venue_id=venue.id).all() if not show.id in all_shows]
      for show in all_shows:
        all_venues.append(show)
  for venue in venues_by_state:
    if Show.query.filter_by(venue_id=venue.id).first():
      all_shows += [show.id for show in Show.query.filter_by(venue_id=venue.id).all() if not show.id in all_shows]
      for show in all_shows:
        all_venues.append(show)

  # Get show object if show.id in list "all_artists" or "all_venues"
  shows_by_artist = db.session.query(Show).filter(Show.id.in_(all_artists)).all()
  shows_by_venue = db.session.query(Show).filter(Show.id.in_(all_venues)).all()
  data = []
  # Use show object to fetch artist and venue objects and populate all necessary data to dictionary "data"
  for show in shows_by_artist:
      artist = Artist.query.filter_by(id=show.artist_id).first()
      venue = Venue.query.filter_by(id=show.venue_id).first()
      data.append({
        'venue_name': venue.name,
        'artist_name': artist.name,
        'artist_image_link': artist.image_link,
        'start_time': str(show.start_time),
        'artist_id': show.artist_id,
        'venue_id': show.venue_id
      })
  for show in shows_by_venue:
      artist = Artist.query.filter_by(id=show.artist_id).first()
      venue = Venue.query.filter_by(id=show.venue_id).first()
      data.append({
        'venue_name': venue.name,
        'artist_name': artist.name,
        'artist_image_link': artist.image_link,
        'start_time': str(show.start_time),
        'artist_id': show.artist_id,
        'venue_id': show.venue_id
      })
  # Pass "data" to results
  results = {
      'shows': data,
      'count': len(data)
  }
  return render_template('pages/show.html', results=results, search_term=request.form.get('search_term'))

@app.route('/shows/create')
def create_shows():
  form = ShowForm()
  return render_template('forms/new_show.html', form=form)

@app.route('/shows/create', methods=['POST'])
def create_show_submission():
  error = False
  message = ''
  venue_id = request.form.get('venue_id')
  artist_id = request.form.get('artist_id')
  start_time = request.form.get('start_time')
  x = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
  # Compare show time with artist's availabilities
  if request.method == 'POST':
    availabilities = Availability.query.filter_by(artist_id=artist_id).all()
    times = []
  # Reference https://stackoverflow.com/questions/796008/cant-subtract-offset-naive-and-offset-aware-datetimes
    for a in availabilities:
      if not a.start_time.replace(tzinfo=None) < x.time() < a.end_time.replace(tzinfo=None):
        times.append(False)
      else:
        times.append(True)
  # If show time is within one available time slot
  if True in times:
    try:
      show = Show(
          venue_id=venue_id,
          artist_id=artist_id,
          start_time=start_time,
      )
      db.session.add(show)
      db.session.commit()
    except:
      error = True
      db.session.rollback()
    finally:
      db.session.close()
    if error:
      flash('An error occured. Show could not be listed.')
    else:
      flash('Show was successfully listed!')
  # Else flash error that artist is unavailable
  else:
    flash('Artist is unavailable during this time.')
  return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
