#!/usr/bin/python
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""All request handlers of PhotoHunt, including its built-in API."""
import logging
import time
import httplib2
import model
import logging
import json
import os
import random
import string
import apiclient
import webapp2
import datetime
from webapp2_extras import jinja2
import re
from apiclient.discovery import build
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from google.appengine.api import urlfetch
from google.appengine.api.app_identity import get_default_version_hostname
import oauth2client
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from webapp2_extras import sessions
import jinja2
from webapp2_extras import i18n

jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),cache_size=0,
  extensions=['jinja2.ext.i18n'])

jinja_environment.install_gettext_translations(i18n)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

SCOPES = [
    'https://www.googleapis.com/auth/plus.login'
]

VISIBLE_ACTIONS = [
    'http://schemas.google.com/AddActivity',
    'http://schemas.google.com/ReviewActivity'
]

TOKEN_INFO_ENDPOINT = ('https://www.googleapis.com/oauth2/v1/tokeninfo' +
    '?access_token=%s')
TOKEN_REVOKE_ENDPOINT = 'https://accounts.google.com/o/oauth2/revoke?token=%s'

class BaseHandler(webapp2.RequestHandler):
    def set_user_locale(self):
        # Get user's Localization settings
        locale = self.request.GET.get('locale', 'en_US')
        i18n.get_i18n().set_locale('en')
      



   

class SessionEnabledHandler(webapp2.RequestHandler):
  """Base type which ensures that derived types always have an HTTP session."""
  CURRENT_USER_SESSION_KEY = 'me'

  def dispatch(self):
    """Intercepts default request dispatching to ensure that an HTTP session
    has been created before calling dispatch in the base type.
    """
    # Get a session store for this request.
    self.session_store = sessions.get_store(request=self.request)
    try:
      # Dispatch the request.
      webapp2.RequestHandler.dispatch(self)
    finally:
      # Save all sessions.
      self.session_store.save_sessions(self.response)

  @webapp2.cached_property
  def session(self):
    """Returns a session using the default cookie key."""
    return self.session_store.get_session()

  def get_user_from_session(self):
    """Convenience method for retrieving the users crendentials from an
    authenticated session.
    """
    google_user_id = self.session.get(self.CURRENT_USER_SESSION_KEY)
    if google_user_id is None:
      raise UserNotAuthorizedException('Session did not contain user id.')
    user = model.User.query(model.User.google_user_id == google_user_id).get()
    
    #if not user:
    # raise UserNotAuthorizedException(
    #   'Session user ID could not be found in the datastore.')
    return user


class UserNotAuthorizedException(Exception):
  msg = 'Unauthorized request.'

class NotFoundException(Exception):
  msg = 'Resource not found.'

class RevokeException(Exception):
  msg = 'Failed to revoke token for given user.'


class JsonRestHandler(webapp2.RequestHandler):
  """Base RequestHandler type which provides convenience methods for writing
  JSON HTTP responses.
  """
  JSON_MIMETYPE = "application/json"

  def send_error(self, code, message):
    """Convenience method to format an HTTP error response in a standard format.
    """
    self.response.set_status(code, message)
    self.response.out.write(message)
    return

  def send_success(self, obj=None, jsonkind='photohunt#unknown'):
    """Convenience method to format a PhotoHunt JSON HTTP response in a standard
    format.
    """
    self.response.headers["Content-Type"] = self.JSON_MIMETYPE
    if obj is not None:
      if isinstance(obj, basestring):
        self.response.out.write(obj)
      else:
        self.response.out.write(json.dumps(obj, cls=model.JsonifiableEncoder))
class HelloWorldHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            context = {'message': user.google_user_id}
            self.render_response('my_template.html', **context)
        else:
            self.redirect('/sign-in')
class SignInHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            if user:
                self.redirect('/')
        
        # Set the user locale from user's settings
        self.set_user_locale()
        user_id = self.request.get('id')
            # Render the template
        template_values = {'CLIENT_ID': CLIENT_ID,
                               'ID' : user_id
                              }
        template = jinja_environment.get_template('templates/sign-in.html')
        self.response.out.write(template.render(template_values))
          
class SignUpHandler(BaseHandler, SessionEnabledHandler):
    
    @staticmethod
    def init_drive_folder(credentials,folder_name,parent=None):
      """Return the public Google+ profile data for the given user."""
      http = httplib2.Http()
      driveservice = build('drive', 'v2', http=http)
      credentials.authorize(http)
      folder = {
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'          
      }
      if parent:
        folder['parents'] = [{'id': parent}]
      try:
        created_folder = driveservice.files().insert(body=folder).execute()
        return created_folder['id']
      except errors.HttpError, error:
        print 'An error occured: %s' % error
        return None   
      
      
    def get(self):
          if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
        
        
            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            
            template_values = {
              'userinfo': user,
              'CLIENT_ID': CLIENT_ID}
            template = jinja_environment.get_template('templates/sign-up.html')
            self.response.out.write(template.render(template_values))
          else:
            self.redirect('/sign-in')
    def post(self):
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            org_name = self.request.get('org_name')
            mob_phone = self.request.get('mob_phone')
            # init organization folders in Google drive
            credentials = user.google_credentials
            org_folder = self.init_drive_folder(credentials,org_name+' (ioGrow)')
            accounts_folder = self.init_drive_folder(credentials,'Accounts', org_folder)
            contacts_folder = self.init_drive_folder(credentials,'Contacts', org_folder)
            leads_folder = self.init_drive_folder(credentials,'Leads', org_folder)
            opportunities_folder = self.init_drive_folder(credentials,'Opportunities', org_folder)
            cases_folder = self.init_drive_folder(credentials,'Cases', org_folder)
            shows_folder = self.init_drive_folder(credentials,'Shows', org_folder)
            organization = model.Organization(name=org_name,
                                              org_folder=org_folder,
                                              accounts_folder=accounts_folder,
                                              contacts_folder=contacts_folder,
                                              leads_folder=leads_folder,
                                              opportunities_folder=opportunities_folder,
                                              cases_folder=cases_folder,
                                              shows_folder=shows_folder)
            organization.put()
            profile = model.Profile.query(model.Profile.name=='Super Administrator', model.Profile.organization==organization.key).get()
            user.init_user_config(organization.key,profile.key)
            self.redirect('/')
        else:
            self.redirect('/sign-in')
class AccountListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/accounts/list.html')
            self.response.out.write(template.render(template_values))

class AccountShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/accounts/show.html')
            self.response.out.write(template.render(template_values))
class ContactListHandler(BaseHandler, SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/contacts/list.html')
      self.response.out.write(template.render(template_values))
class ContactShowHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/contacts/show.html')
      self.response.out.write(template.render(template_values))
class OpportunityListHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values = {'tabs':tabs}
      template = jinja_environment.get_template('templates/opportunities/opportunity_list.html')
      self.response.out.write(template.render(template_values))
class OpportunityShowHandler(BaseHandler,SessionEnabledHandler):
  def get (self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/opportunities/opportunity_show.html')
      self.response.out.write(template.render(template_values))

class LeadListHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values = {'tabs':tabs}
      template = jinja_environment.get_template('templates/leads/lead_list.html')
      self.response.out.write(template.render(template_values))
class LeadShowHandler(BaseHandler,SessionEnabledHandler):
  def get (self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/leads/lead_show.html')
      self.response.out.write(template.render(template_values))

class CaseListHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values = {'tabs':tabs}
      template = jinja_environment.get_template('templates/cases/case_list.html')
      self.response.out.write(template.render(template_values))
class CaseShowHandler(BaseHandler,SessionEnabledHandler):
  def get (self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/cases/case_show.html')
      self.response.out.write(template.render(template_values))
class CampaignListHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values = {'tabs':tabs}
      template = jinja_environment.get_template('templates/campaigns/campaign_list.html')
      self.response.out.write(template.render(template_values))
class CampaignShowHandler(BaseHandler,SessionEnabledHandler):
  def get (self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/campaigns/campaign_show.html')
      self.response.out.write(template.render(template_values))
class NoteShowHandler (BaseHandler,SessionEnabledHandler):
  def get(self):
    if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
      user = self.get_user_from_session()
      self.set_user_locale()
      tabs = user.get_user_active_tabs()
      self.set_user_locale()
      template_values={'tabs':tabs}
      template = jinja_environment.get_template('templates/accounts/note_show.html')
      self.response.out.write(template.render(template_values))
   

class ShowListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/shows/list.html')
            self.response.out.write(template.render(template_values))
class ShowShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/shows/show.html')
            self.response.out.write(template.render(template_values))
class UserListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/admin/users/list.html')
            self.response.out.write(template.render(template_values))

class GroupListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/admin/groups/list.html')
            self.response.out.write(template.render(template_values))

class GroupShowHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/admin/groups/show.html')
            self.response.out.write(template.render(template_values))

class GooglePlusConnect(SessionEnabledHandler):
    @staticmethod
    def exchange_code(code):
      """Exchanges the `code` member of the given AccessToken object, and returns
      the relevant credentials.

      Args:
        code: authorization code to exchange.

      Returns:
        Credentials response from Google indicating token information.

      Raises:
        FlowExchangeException Failed to exchange code (code invalid).
      """
      oauth_flow = flow_from_clientsecrets('client_secrets.json',
        scope='')
      oauth_flow.request_visible_actions = ' '.join(VISIBLE_ACTIONS)
      oauth_flow.redirect_uri = 'postmessage'
      credentials = oauth_flow.step2_exchange(code)
      return credentials
    @staticmethod
    def get_token_info(credentials):
      """Get the token information from Google for the given credentials."""
      url = (TOKEN_INFO_ENDPOINT
             % credentials.access_token)
      return urlfetch.fetch(url)

    @staticmethod
    def get_user_profile(credentials):
      """Return the public Google+ profile data for the given user."""
      http = httplib2.Http()
      plus = build('plus', 'v1', http=http)
      credentials.authorize(http)
      return plus.people().get(userId='me').execute()
    @staticmethod
    def get_user_email(credentials):
      """Return the public Google+ profile data for the given user."""
      http = httplib2.Http()
      userinfo = build('oauth2', 'v1', http=http)
      credentials.authorize(http)
      return userinfo.userinfo().get().execute()

    @staticmethod
    def save_token_for_user(google_user_id, credentials,user_id=None):
      """Creates a user for the given ID and credential or updates the existing
      user with the existing credential.

      Args:
        google_user_id: Google user ID to update.
        credentials: Credential to set for the user.

      Returns:
        Updated User.
      """
      if user_id:
        user = model.User.get_by_id(user_id)
        profile = GooglePlusConnect.get_user_profile(credentials)
        email = GooglePlusConnect.get_user_email(credentials)

        
        user.google_user_id = profile.get('id')
        user.google_display_name = profile.get('displayName')
        user.google_public_profile_url = profile.get('url')
        user.email = email.get('email')
        image = profile.get('image')
        if image is not None:
          user.google_public_profile_photo_url = image.get('url')
      else:
        user = model.User.query(model.User.google_user_id == google_user_id).get()     
      #user = model.User.all().filter('google_user_id =', google_user_id).get()
      
      if user is None:
        
        # Couldn't find User in datastore.  Register a new user.
        profile = GooglePlusConnect.get_user_profile(credentials)
        email = GooglePlusConnect.get_user_email(credentials)

        user = model.User()
        user.google_user_id = profile.get('id')
        user.google_display_name = profile.get('displayName')
        user.google_public_profile_url = profile.get('url')
        user.email = email.get('email')
        image = profile.get('image')
        if image is not None:
          user.google_public_profile_photo_url = image.get('url')
      user.google_credentials = credentials
      user.put()
      return user

  
    def post(self):
        #try to get the user credentials from the code
        credentials = None
        code = self.request.get("code")
        try:
            credentials = GooglePlusConnect.exchange_code(code)
        except FlowExchangeError:
            return
        token_info = GooglePlusConnect.get_token_info(credentials)
        if token_info.status_code != 200:
            return
        token_info = json.loads(token_info.content)
        # If there was an error in the token info, abort.
        if token_info.get('error') is not None:
            return
        # Make sure the token we got is for our app.
        expr = re.compile("(\d*)(.*).apps.googleusercontent.com")
        issued_to_match = expr.match(token_info.get('issued_to'))
        local_id_match = expr.match(CLIENT_ID)
        if (not issued_to_match
            or not local_id_match
            or issued_to_match.group(1) != local_id_match.group(1)):
          
            return

        
        
        
        
        #Check if is it an invitation to sign-in or just a simple sign-in 
        invited_user_id = None
        invited_user_id_request = self.request.get("id")
        if invited_user_id_request:
            invited_user_id = long(invited_user_id_request)
        user = model.User.query(model.User.google_user_id == token_info.get('user_id')).get()
        isNewUser = False
        if user is None:
            isNewUser = True
        # Store our credentials with in the datastore with our user.
        if invited_user_id:

          user = GooglePlusConnect.save_token_for_user(token_info.get('user_id'),
                                                  credentials,invited_user_id)
        else:

          user = GooglePlusConnect.save_token_for_user(token_info.get('user_id'),
                                                  credentials)
        # if user does not exist redirect him to sign-up
        

        # Store the user ID in the session for later use.
        self.session[self.CURRENT_USER_SESSION_KEY] = token_info.get('user_id')
        self.response.headers['Content-Type'] = 'application/json'  
        self.response.out.write(json.dumps(isNewUser))




class DisconnectHandler(JsonRestHandler, SessionEnabledHandler):
  """Provides an API to disconnect users from Photohunt.

  This handler provides the /api/disconnect endpoint, and exposes the following
  operations:
    POST /api/disconnect
  """

  @staticmethod
  def revoke_token(credentials):
    """Revoke the given access token, and consequently any other access tokens
    and refresh tokens issued for this user to this app.

    Essentially this operation disconnects a user from the app, but keeps
    their app activities alive in Google.  The same user can later come back
    to the app, sign-in, re-consent, and resume using the app.
    throws RevokeException error occured while making request.
    """
    url = TOKEN_REVOKE_ENDPOINT % credentials.access_token
    http = httplib2.Http()
    credentials.authorize(http)
    result = http.request(url, 'GET')[0]

    if result['status'] != '200':
      raise RevokeException

  def post(self):
    """Exposed as `POST /api/disconnect`.

    As required by the Google+ Platform Terms of Service, this end-point:

      1. Deletes all data retrieved from Google that is stored in our app.
      2. Revokes all of the user's tokens issued to this app.

    Takes no request payload, and disconnects the user currently identified
    by their session.

    Returns the following JSON response representing the User that was
    connected:

      'Successfully disconnected.'

    Issues the following errors along with corresponding HTTP response codes:
    401: 'Unauthorized request'.  No user was connected to disconnect.
    500: 'Failed to revoke token for given user: '
         + error from failed connection to revoke end-point.
    """
    try:
      user = self.get_user_from_session()
      credentials = user.google_credentials

      del(self.session[self.CURRENT_USER_SESSION_KEY])
      user_id = user.key().id()
      db.delete(model.Vote.all().filter("owner_user_id =", user_id).run())
      db.delete(model.Photo.all().filter("owner_user_id =", user_id).run())
      db.delete(model.DirectedUserToUserEdge.all().filter(
          "owner_user_id =", user_id).run())
      db.delete(user)

      DisconnectHandler.revoke_token(credentials)
      self.send_success('Successfully disconnected.')
      return
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)
      return
    except RevokeException as e:
      self.send_error(500, e.msg)
      return

class SearchListHandler(BaseHandler, SessionEnabledHandler):
    def get(self):
      if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # Set the user locale from user's settings
            self.set_user_locale()
            tabs = user.get_user_active_tabs()

            # Set the user locale from user's settings
            self.set_user_locale()
            # Render the template
            template_values = {'tabs':tabs}
            template = jinja_environment.get_template('templates/search/list.html')
            self.response.out.write(template.render(template_values))

class IndexHandler(BaseHandler,SessionEnabledHandler):
  def get(self):
        
        # Check if the user is loged-in, if not redirect him to the sign-in page
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            try:
                user = self.get_user_from_session()
                if user is None:
                    self.redirect('/sign-in')
                    return
                # Set the user locale from user's settings
                self.set_user_locale()
                apps = user.get_user_apps()
                active_app = user.get_user_active_app()
                print active_app
                

                template_values = {
                  'CLIENT_ID': CLIENT_ID,
                  'active_app':active_app,
                                  'apps': apps,
                }
                template = jinja_environment.get_template('templates/base.html')
                self.response.out.write(template.render(template_values))
            except UserNotAuthorizedException as e:
                self.redirect('/sign-in')
        else:
            self.redirect('/sign-in')
class ChangeActiveAppHandler(SessionEnabledHandler):
  
  def get(self,appid):
        new_app_id = int(appid)
        if self.session.get(SessionEnabledHandler.CURRENT_USER_SESSION_KEY) is not None:
            user = self.get_user_from_session()
            # get the active application before the change request
            active_app = user.get_user_active_app()
            new_active_app = model.Application.get_by_id(new_app_id)
            if new_active_app:
              if new_active_app.organization==user.organization:
                future = user.set_user_active_app(new_active_app.key)
                # To-do resolve this: we are waiting for the active_app to be refreshed
                #time.sleep(1)
                self.redirect(new_active_app.url)
                future.get_result()
              else:
                self.redirect('/error')
            else:
              self.redirect('/')

            
        else:
            self.redirect('/sign-in')
           
        

class FriendsHandler(JsonRestHandler, SessionEnabledHandler):
  """Provides an API for working with Users.

  This handler provides the /api/friends end-point, and exposes the following
  operations:
    GET /api/friends
  """

  def get(self):
    """Exposed as `GET /api/friends`.

    Takes no request payload, and identifies the incoming user by the user
    data stored in their session.

    Returns the following JSON response representing the people that are
    connected to the currently signed in user:
    [
      {
        'id':0,
        'googleUserId':'',
        'googleDisplayName':'',
        'googlePublicProfileUrl':'',
        'googlePublicProfilePhotoUrl':'',
        'googleExpiresAt':0
      },
         ...
    ]

    Issues the following errors along with corresponding HTTP response codes:
    401: 'Unauthorized request'
    """
    try:
      user = self.get_user_from_session()
      friends = user.get_friends()
      self.send_success(friends, jsonkind="photohunt#friends")
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)

class ImageHandler(JsonRestHandler, SessionEnabledHandler):
  """Provides an API for creating and retrieving URLs to which photo images can
  be uploaded.

  This handler provides the /api/images end-point, and exposes the following
  operations:
    POST /api/images
  """

  def post(self):
    """Exposed as `POST /api/images`.

    Creates and returns a URL that can be used to upload an image for a
    photo. Returned URL, after receiving an upload, will fire a callback
    (resend the entire HTTP request) to /api/photos.

    Takes no request payload.

    Returns the following JSON response representing an upload URL:

    {
      "url": "http://appid.appspot.com/_ah/upload/upload-key"
    }

    Issues the following errors along with corresponding HTTP response codes:
    401: 'Unauthorized request'
    """
    user = self.get_user_from_session()
    upload_url_string = blobstore.create_upload_url('/api/photos')
    self.send_success(model.UploadUrl(url = upload_url_string))

  def get(self):
    """Serve an image."""
    photo_id = self.request.get('id')
    photo = model.Photo.all().filter('id=', photo_id).get()
    self.response.headers['Content-Type'] = 'image/png'
    self.response.out.write(photo.image_blob)


class PhotosHandler(JsonRestHandler, SessionEnabledHandler,
    blobstore_handlers.BlobstoreUploadHandler):
  """Provides an API for working with Photos.

  This handler provides the /api/photos endpoint, and exposes the following
  operations:
    GET /api/photos
    GET /api/photos?photoId=1234
    GET /api/photos?themeId=1234
    GET /api/photos?userId=me
    GET /api/photos?themeId=1234&userId=me
    GET /api/photos?themeId=1234&userId=me&friends=true
    POST /api/photos
    DELETE /api/photos?photoId=1234
  """

  def get(self):
    """Exposed as `GET /api/photos`.

    Accepts the following request parameters.

    'photoId': id of the requested photo. Will return a single Photo.
    'themeId': id of a theme. Will return the collection of photos for the
               specified theme.
     'userId': id of the owner of the photo. Will return the collection of
               photos for that user. The keyword 'me' can be used and will be
               converted to the logged in user. Requires auth.
    'friends': value evaluated to boolean, if true will filter only photos
               from friends of the logged in user. Requires auth.

    Returns the following JSON response representing a list of Photos.

    [
      {
        'id':0,
        'ownerUserId':0,
        'ownerDisplayName':'',
        'ownerProfileUrl':'',
        'ownerProfilePhoto':'',
        'themeId':0,
        'themeDisplayName':'',
        'numVotes':0,
        'voted':false, // Whether or not the current user has voted on this.
        'created':0,
        'fullsizeUrl':'',
        'thumbnailUrl':'',
        'voteCtaUrl':'', // URL for Vote interactive post button.
        'photoContentUrl':'' // URL for Google crawler to hit to get info.
      },
      ...
    ]

    Issues the following errors along with corresponding HTTP response codes:
    401: 'Unauthorized request' (if certain parameters are present in the
    request)
    """
    try:
      photo_id = self.request.get('photoId')
      theme_id = self.request.get('themeId')
      user_id = self.request.get('userId')
      show_friends = bool(self.request.get('friends'))
      query = model.Photo.all()
      if photo_id:
        photo = model.Photo.get_by_id(long(photo_id))
        self.send_success(photo)
        return
      else:
        if user_id:
          if user_id == 'me':
            user = self.get_user_from_session()
          else:
            user = model.User.get_by_id(long(user_id))
          if show_friends:
            user = self.get_user_from_session()
            friends = user.get_friends()
            if len(friends) > 0:
              query = query.filter('owner_user_id in', friends[0:30])
            else:
              self.send_success([])
              return
          else:
            query = query.filter('owner_user_id =', user.key().id())

      if theme_id:
        query = query.filter('theme_id =', long(theme_id))

      photos = list(query.run())

      if self.session.get(self.CURRENT_USER_SESSION_KEY) is not None:
        if not user_id:
          user = self.get_user_from_session()

        votes = model.Vote.all().filter(
            "owner_user_id =", user.key().id()).run()
        photo_votes = []
        for vote in votes:
          photo_votes.append(vote.photo_id)
        for photo in photos:
          photo.voted = photo.key().id() in photo_votes

      self.send_success(photos, jsonkind='photohunt#photos')
    except TypeError as te:
      self.send_error(404, "Resource not found")
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)

  def post(self):
    """Exposed as `POST /api/photos`.

    Takes the following payload in the request body.  Payload represents a
    Photo that should be created.
    {
      'id':0,
      'ownerUserId':0,
      'ownerDisplayName':'',
      'ownerProfileUrl':'',
      'ownerProfilePhoto':'',
      'themeId':0,
      'themeDisplayName':'',
      'numVotes':0,
      'voted':false, // Whether or not the current user has voted on this.
      'created':0,
      'fullsizeUrl':'',
      'thumbnailUrl':'',
      'voteCtaUrl':'', // URL for Vote interactive post button.
      'photoContentUrl':'' // URL for Google crawler to hit to get info.
    }

    Returns the following JSON response representing the created Photo.
    {
      'id':0,
      'ownerUserId':0,
      'ownerDisplayName':'',
      'ownerProfileUrl':'',
      'ownerProfilePhoto':'',
      'themeId':0,
      'themeDisplayName':'',
      'numVotes':0,
      'voted':false, // Whether or not the current user has voted on this.
      'created':0,
      'fullsizeUrl':'',
      'thumbnailUrl':'',
      'voteCtaUrl':'', // URL for Vote interactive post button.
      'photoContentUrl':'' // URL for Google crawler to hit to get info.
    }

    Issues the following errors along with corresponding HTTP response codes:
    400: 'Bad Request' if the request is missing image data.
    401: 'Unauthorized request' (if certain parameters are present in the
         request)
    401: 'Access token expired' (there is a logged in user, but he doesn't
         have a refresh token and his access token is expiring in less than
         100 seconds, get a new token and retry)
    500: 'Error while writing app activity: ' + error from client library.
    """
    try:
      user = self.get_user_from_session()
      current_theme = model.Theme.get_current_theme()
      if current_theme:
        uploads = self.get_uploads('image')
        blob_info = uploads[0]
        photo = model.Photo(owner_user_id=user.key().id(),
            owner_display_name=user.google_display_name,
            owner_profile_photo=user.google_public_profile_photo_url,
            owner_profile_url=user.google_public_profile_url,
            theme_id=current_theme.key().id(),
            theme_display_name=current_theme.display_name,
            created=datetime.datetime.now(),
            num_votes=0,
            image_blob_key=blob_info.key())
        photo.put()
        try:
          result = self.add_photo_to_google_plus_activity(user, photo)
        except apiclient.errors.HttpError as e:
          logging.error("Error while writing app activity: %s", str(e))
        self.send_success(photo)
      else:
        self.send_error(404, 'No current theme.')
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)

  def delete(self):
    """Exposed as `DELETE /api/photos`.

    Accepts the following request parameters.

    'photoId': id of the photo to delete.

    Returns the following JSON response representing success.
    'Photo successfully deleted.'

    Issues the following errors along with corresponding HTTP response codes:
    401: 'Unauthorized request' (if certain parameters are present in the
         request)
    404: 'Photo with given ID does not exist.'
    """
    try:
      user = self.get_user_from_session()
      photo_id = self.request.get('photoId')
      if photo_id:
        photo = model.Photo.get_by_id(long(photo_id))
        if photo.owner_user_id != user.key().id():
          raise UserNotAuthorizedException
        photoVotes = model.Vote.all().filter(
          "photo_id =", photo.key().id()).run()
        db.delete(photo)
        db.delete(photoVotes)
        self.send_success(model.Message(message = "Photo successfully deleted"))
      else:
        raise NotFoundException
    except NotFoundException as nfe:
      self.send_error(404, nfe.msg)
    except TypeError as te:
      self.send_error(404, "Resource not found")
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)

  def add_photo_to_google_plus_activity(self, user, photo):
    """Creates an app activity in Google indicating that the given User has
    uploaded the given Photo.

    Args:
      user: Creator of Photo.
      photo: Photo itself.
    """
    activity = {"type":"http://schemas.google.com/AddActivity",
              "target": {
                "url": photo.photo_content_url
              }}
    logging.debug("activity: " + str(activity))
    http = httplib2.Http()
    plus = build('plus', 'v1', http=http)
    if user.google_credentials:
      http = user.google_credentials.authorize(http)
    return plus.moments().insert(userId='me', collection='vault',
                                    body=activity).execute()

class ThemesHandler(JsonRestHandler):
  """Provides an API for working with Themes.

  This handler provides the /api/themes end-point, and exposes the following
  operations:
    GET /api/themes
  """

  def get(self):
    """Exposed as `GET /api/themes`.

    When requested, if no theme exists for the current day, then a theme with
    the name of 'Beautiful' is created for today.  This leads to multiple
    themes with the name 'Beautiful' if you use the app over multiple days
    without changing this logic.  This behavior is purposeful so that the app
    is easier to get up and running.

    Returns the following JSON response representing a list of Themes.

    [
      {
        'id':0,
        'displayName':'',
        'created':0,
        'start':0
      },
      ...
    ]
    """
    themes = list(model.Theme.all().order('-start').run())
    if not themes:
      default_theme = model.Theme(display_name="Beautiful")
      default_theme.start = default_theme.created
      default_theme.put()
      themes = [default_theme]
    self.send_success(themes, jsonkind="photohunt#themes")

class VotesHandler(JsonRestHandler, SessionEnabledHandler):
  """Provides an API for working with Votes.  This servlet provides the
     /api/votes end-point, and exposes the following operations:

       PUT /api/votes
  """

  def put(self):
    """Exposed as `PUT /api/votes`.

       Takes a request payload that is a JSON object containing the Photo ID
       for which the currently logged in user is voting.

       {
         'photoId':0
       }

       Returns the following JSON response representing the Photo for which the
       User voted.

       {
         'id':0,
         'ownerUserId':0,
         'ownerDisplayName':'',
         'ownerProfileUrl':'',
         'ownerProfilePhoto':'',
         'themeId':0,
         'themeDisplayName':'',
         'numVotes':1,
         'voted':true,
         'created':0,
         'fullsizeUrl':'',
         'thumbnailUrl':'',
         'voteCtaUrl':'',
         'photoContentUrl':''
       }

       Issues the following errors along with corresponding HTTP response codes:
       401: 'Unauthorized request'.  No user was connected to disconnect.
       401: 'Access token expired'.  Retry with a new access token.
       500: 'Error writing app activity: ' + error from client library
    """
    try:
      user = self.get_user_from_session()
      vote = model.Vote()
      vote.from_json(self.request.body)
      vote.owner_user_id = user.key().id()
      voteExist = model.Vote.all().filter(
          "owner_user_id =", user.key().id()).filter(
          "photo_id =", vote.photo_id).get()
      if voteExist is None:
        photo = model.Photo.get_by_id(vote.photo_id)
        if photo is not None:
          vote.put()
          photo.voted = True
          self.add_photo_to_google_plus_activity(user, photo)
          self.send_success(photo)
          return
    except UserNotAuthorizedException as e:
      self.send_error(401, e.msg)

  def add_photo_to_google_plus_activity(self, user, photo):
    """Add to the user's Google+ app activity that they voted on photo.

    Args:
      user: User voting.
      photo: Photo being voted on.
    """
    activity = {"type":"http://schemas.google.com/ReviewActivity",
              "target": {
                "url": photo.photo_content_url
              },
              "result": {
                "type": "http://schema.org/Review",
                "name": "A vote for a PhotoHunt photo",
                "url": photo.photo_content_url,
                "text": "Voted!"
              }}
    http = httplib2.Http()
    plus = build('plus', 'v1', http=http)
    if user.google_credentials:
      http = user.google_credentials.authorize(http)
    return plus.moments().insert(userId='me', collection='vault',
                                    body=activity).execute()


class SchemaHandler(JsonRestHandler, SessionEnabledHandler):
  """Returns metadata for an image for user when writing moments."""

  def get(self):
    """Returns the template at templates/${request.path}.

       Issues the following errors along with corresponding HTTP response codes:
       404: 'Not Found'. No template was found for the specified path.
    """
    try:
      photo_id = self.request.get('photoId')
      self.response.headers['Content-Type'] = 'text/html'
      template = jinja_environment.get_template('templates' + self.request.path)
      if photo_id:
        photo = model.Photo.get_by_id(long(photo_id))
        self.response.out.write(template.render({
          'photoId': photo_id,
          'redirectUrl': 'index.html?photoId={}'.format(photo_id),
          'name': 'Photo by {} for {} | PhotoHunt'.format(
              photo.owner_display_name,
              photo.theme_display_name),
          'imageUrl': photo.thumbnail_url,
          'description': '{} needs your vote to win this hunt.'.format(
              photo.owner_display_name)
        }))
      else:
        photo = model.Photo.all().get()
        if photo:
          self.response.out.write(template.render({
            'redirectUrl': 'index.html?photoId='.format(photo_id),
            'name': 'Photo by {} for {} | PhotoHunt'.format(
                photo.owner_display_name,
                photo.theme_display_name),
            'imageUrl': photo.thumbnail_url,
            'description': 'Join in the PhotoHunt game.'
          }))
        else:
          self.response.out.write(template.render({
            'redirectUrl': get_base_url(),
            'name': 'PhotoHunt',
            'imageUrl': '{}/images/interactivepost-icon.png'.format(
                get_base_url()),
            'description': 'Join in the PhotoHunt game.'
          }))
    except TypeError as te:
      self.send_error(404, "Resource not found")


def get_base_url():
  """Returns the base URL for this application."""
  base = get_default_version_hostname()
  if "appspot.com" in base:
    return "https://%s" % base
  return "http://%s" % base

routes = [
    ('/',IndexHandler),
    (r'/apps/(\d+)', ChangeActiveAppHandler),
    # Templates Views Routes
    ('/views/accounts/list',AccountListHandler),
    ('/views/accounts/show',AccountShowHandler),
    ('/views/contacts/list',ContactListHandler),
    ('/views/contacts/show',ContactShowHandler),

    ('/views/shows/list',ShowListHandler),
    ('/views/shows/show',ShowShowHandler),

    ('/views/opportunities/list',OpportunityListHandler),
    ('/views/opportunities/show',OpportunityShowHandler),
    ('/views/leads/list',LeadListHandler),
    ('/views/leads/show',LeadShowHandler),
    ('/views/cases/list',CaseListHandler),
    ('/views/cases/show',CaseShowHandler),
    ('/views/campaigns/list',CampaignListHandler),
    ('/views/campaigns/show',CampaignShowHandler),
    ('/views/notes/show',NoteShowHandler),
    ('/views/search/list',SearchListHandler),
    
    ('/views/admin/users/list',UserListHandler),
    ('/views/admin/groups/list',GroupListHandler),
    ('/views/admin/groups/show',GroupShowHandler),
    ('/hello',HelloWorldHandler),
    ('/sign-in',SignInHandler),
    ('/sign-up',SignUpHandler),
    ('/gconnect',GooglePlusConnect)
    ]
config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'YOUR_SESSION_SECRET'
}
app = webapp2.WSGIApplication(routes, config=config, debug=True)
