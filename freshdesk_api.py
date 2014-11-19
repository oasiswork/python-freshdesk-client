import json
import urlparse
import requests


# Freshdesk uses some exotic return codes

HTTP_ALREADY_EXISTS = 422

class FreshDeskObjects(object):
    """ Abstract class to wrap a type of freshdesk resource.
    """
    def __init__(self, client):
        self.client = client

    def api_endpoint(self, id=None):
        if id:
            return '/{}s/{}.json'.format(self.api_name, id)
        else:
            return '/{}s.json'.format(self.api_name)

    # CRUD methods

    def create(self, **kwargs):
        return self.client.req(
            requests.post, self.api_endpoint(), self.wrapper_name,
            **kwargs)

    def update(self, id, **kwargs):
        return self.client.req(
            requests.put, self.api_endpoint(id), self.wrapper_name,
            **kwargs)

    def delete(self, id):
        return self.client.req(
            requests.delete, self.api_endpoint(id), self.wrapper_name)

    def get(self, id):
        return self.client.req(
            requests.get, self.api_endpoint(id), self.wrapper_name,
            id=id)

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
                requests.get, self.api_endpoint(), self.wrapper_name,
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
    api_name = 'contact'
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
    api_name = 'customer'
    wrapper_name = api_name

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
                    return [i[resource_type] for i in json_obj]
                else:
                    return json_obj[resource_type]
        else:
            raise self.APIError(resp)

