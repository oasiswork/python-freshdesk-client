import json
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse
import requests


# Freshdesk uses some exotic return codes

HTTP_ALREADY_EXISTS = 422

class FreshDeskObjects(object):
    """ Abstract class to wrap a type of freshdesk resource.
    """
    def __init__(self, client):
        self.client = client

    def api_endpoint(self, prefix, id=None):
        if id:
            return '{}/{}/{}.json'.format(prefix, self.api_name, id)
        else:
            return '{}/{}.json'.format(prefix, self.api_name)

    # CRUD methods

    def create(self, prefix='', **kwargs):
        return self.client.req(
            requests.post, self.api_endpoint(prefix=prefix), self.wrapper_name,
            **kwargs)

    def update(self, id, prefix='', **kwargs):
        return self.client.req(
            requests.put, self.api_endpoint(id=id, prefix=prefix), self.wrapper_name,
            **kwargs)

    def delete(self, id, prefix=''):
        return self.client.req(
            requests.delete, self.api_endpoint(id=id, prefix=prefix), self.wrapper_name)

    def get(self, id, prefix='',):
        return self.client.req(
            requests.get, self.api_endpoint(id=id, prefix=prefix), self.wrapper_name)

    def get_list(self, remove_pagination=False, **params):
        """
        :type  remove_pagination boolean
        :param remove_pagination if True, will fetch all pages and present
                                 result as a single list (use with caution)
        :rtype                   a list of dicts
        """
        full_list = []
        page = 1
        while True:
            resp = self.client.req(
                requests.get, self.api_endpoint(prefix=''), self.wrapper_name,
                params=params)
            full_list += resp
            if len(resp) <= 0 or not remove_pagination:
                break
            else:
                page += 1
                params['page'] = page

        return full_list


class FreshDeskContacts(FreshDeskObjects):
    """ http://freshdesk.com/api#user
    """
    api_name = 'contacts'
    wrapper_name = 'user'

    # Status names (default is state=verified)
    DELETED    = 'deleted'
    ALL        = 'all'         # Do not include deleted accounts
    VERIFIED   = 'verified'
    UNVERIFIED = 'unverified'

    def create(self, name, email, **kwargs):
        return super(FreshDeskContacts, self).create(name=name, email=email, **kwargs)

    def create_or_enable(self, name, email, **kwargs):
        """ If creation fails because user exists in deleted state, restore it.

        Freshdesk do not allow two users with same email, even if the collision
        is with a deleted user.
        """
        try:
            return self.create(name=name, email=email, **kwargs)
        except FreshDeskClient.APIError as e:
            contacts = self.get_list(
                state='deleted', query='email is {}'.format(email))
            if ((len(contacts) > 0) and
                (e.resp.status_code == HTTP_ALREADY_EXISTS)):
                contact = contacts[0]
                self.update(contact['id'], name=name, deleted=False, **kwargs)
                # update local version as well
                contact[name] = name
                contact.update(kwargs)

                return contact
            else:
                raise

    def get_or_create(self, name, email, **kwargs):
        """ Try to get the contact by email, and creates it if it do not exist.

        :returns a boolean (true if created) and the object dict itself
        """
        try:
            obj = self.create_or_enable(name, email, **kwargs)
            created = True
        except FreshDeskClient.APIError as e:
            if e.resp.status_code == HTTP_ALREADY_EXISTS:
                contacts = self.get_list(
                    state='all', query='email is {}'.format(email))
                obj = contacts[0]
                created = False
            else:
                raise
        return created, obj


class FreshDeskCustomers(FreshDeskObjects):
    """ http://freshdesk.com/api#companies
    """
    api_name = 'customers'
    wrapper_name = 'customer'

    def create(self, name, **kwargs):
        return super(FreshDeskCustomers, self).create(name=name, **kwargs)


class FreshDeskClient(object):
    """ Simple wrapper arround freshdesk REST API

    This wrapper is non neutral, it includes Oasiswork policy about default
    settings.

        cli = FreshDeskClient('https://mycompany.freshdesk.com', 'qwertyui')
        cli.contacts.get_list(state='all')

    """
    class APIError(Exception):
        def __init__(self, resp):
            self.resp = resp
        def __str__(self):
            return 'HTTP {}: {}'.format(self.resp.status_code, self.resp.text)

    def __init__(self, url, key):
        """
        :param url  endpoint url, eg: https://yourcompany.freshdesk.com
        :param key  API key
        """
        self.url = url
        self.key = key
        self.last_resp = None

        # Resources types
        self.customers = FreshDeskCustomers(self)
        self.contacts = FreshDeskContacts(self)
        self.solution_categories = FreshDeskSolutionCategories(self)
        self.solution_folders = FreshDeskSolutionFolders(self)
        self.solution_articles = FreshDeskSolutionArticles(self)

    def req(self, func, path, resource_type, params={}, **kwargs):
        abs_url = urlparse.urljoin(self.url, path)

        if func in (requests.patch, requests.put, requests.post):
            req_attrs = {
                'data': json.dumps({resource_type: kwargs}),
                'headers': {'Content-Type': 'application/json'}
            }
        else:
            req_attrs = {}

        resp =  func(
            abs_url,
            auth=(self.key, 'nopassword'),
            params=params,
            **req_attrs)
        self.last_resp = resp
        if resp.ok:
            # for those two types of requests, the output is empty
            if func in (requests.delete, requests.put):
                return resp.text
            else:
                # Either we get a list or a single object
                json_obj = resp.json()
                if isinstance(json_obj, (list, tuple)):
                    try:
                        return [i[resource_type] for i in json_obj]
                    # Freshdesk doesn't return same resource_type as the one
                    # we pushed him (exemple : we push "solution_category", he 
                    # returns "category")
                    except KeyError:
                        resource_type = resource_type.split('_')[1]
                        return [i[resource_type] for i in json_obj]
                else:
                    try:
                        return json_obj[resource_type]
                    except KeyError:
                        resource_type = resource_type.split('_')[1]
                        return json_obj[resource_type]
        else:
            print('DEBUG', path)
            raise self.APIError(resp)

class FreshDeskSolutionCategories(FreshDeskObjects):
    """ http://freshdesk.com/api#solution-category
    """
    api_name = 'categories'
    wrapper_name = 'solution_category'
    url_prefix = 'solution'

    def create(self, **kwargs):
        return super(FreshDeskSolutionCategories, self).create(prefix=self.url_prefix, **kwargs)

    def update(self, id, **kwargs):
        return super(FreshDeskSolutionCategories, self).update(id=id, prefix=self.url_prefix, **kwargs)

    def delete(self, id):
        return super(FreshDeskSolutionCategories, self).delete(id=id, prefix=self.url_prefix)

    def get(self, id):
        return super(FreshDeskSolutionCategories, self).get(id=id, prefix=self.url_prefix)


class FreshDeskSolutionFolders(FreshDeskObjects):
    """ http://freshdesk.com/api#solution-folder
    """
    api_name = 'folders'
    wrapper_name = 'solution_folder'
    url_prefix = 'solution/categories/{}'

    def create(self, category, **kwargs):
        return super(FreshDeskSolutionFolders, self).create(prefix=self.url_prefix.format(category), **kwargs)

    def update(self, category, id, **kwargs):
        return super(FreshDeskSolutionFolders, self).update(id=id, prefix=self.url_prefix.format(category), **kwargs)

    def delete(self, category, id):
        return super(FreshDeskSolutionFolders, self).delete(id=id, prefix=self.url_prefix.format(category))

    def get(self, category, id):
        return super(FreshDeskSolutionFolders, self).get(id=id, prefix=self.url_prefix.format(category))


class FreshDeskSolutionArticles(FreshDeskObjects):
    """ http://freshdesk.com/api#solution-article
    """
    api_name = 'articles'
    wrapper_name = 'solution_article'
    url_prefix = 'solution/categories/{}/folders/{}'

    def create(self, category, folder, **kwargs):
        return super(FreshDeskSolutionArticles, self).create(prefix=self.url_prefix.format(category, folder), **kwargs)

    def update(self, category, folder, id, **kwargs):
        return super(FreshDeskSolutionArticles, self).update(id=id, prefix=self.url_prefix.format(category, folder), **kwargs)

    def delete(self, category, folder, id):
        return super(FreshDeskSolutionArticles, self).delete(id=id, prefix=self.url_prefix.format(category, folder))

    def get(self, category, folder, id):
        return super(FreshDeskSolutionArticles, self).get(id=id, prefix=self.url_prefix.format(category, folder))
