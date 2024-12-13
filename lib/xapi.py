import requests
import logging


class XAPI:
    def __init__(self, x_bearer):
        self.x_bearer = x_bearer

    # Get space metadata. Returns the start time of the space as a Unix timestamp
    def get_space_metadata(self, space_id):
        url = f"https://api.x.com/2/spaces/{space_id}"
        headers = {"Authorization": f"Bearer {self.x_bearer}"}
        params = {"space.fields": "started_at,title"}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json().get("data", {})
            return data

        err_msg = response.text
        logging.error(err_msg)
        raise Exception(err_msg)
