"""Keep test credentials out of the user's OS credential manager, also in CI."""
import keyring
from keyring.backend import KeyringBackend
import pytest

class TestKeyring(KeyringBackend):
    priority=1
    def __init__(self):self.values={}
    def get_password(self,service,username):return self.values.get((service,username))
    def set_password(self,service,username,password):self.values[service,username]=password
    def delete_password(self,service,username):self.values.pop((service,username),None)

@pytest.fixture(scope='session',autouse=True)
def isolated_test_keyring():
    original=keyring.get_keyring()
    keyring.set_keyring(TestKeyring())
    yield
    keyring.set_keyring(original)
