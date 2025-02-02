import pytest
import time

from jose.exceptions import JWTClaimsError

from okta_jwt_verifier import JWTVerifier, AccessTokenVerifier, IDTokenVerifier
from okta_jwt_verifier.exceptions import JWKException, JWTValidationException
from okta_jwt_verifier.request_executor import RequestExecutor


class MockRequestExecutor(RequestExecutor):

    response = {}

    def get(self, uri, **params):
        return MockRequestExecutor.response


def test_construct_jwks_uri():
    # issuer without '/' at the end
    jwt_verifier = JWTVerifier('https://test_issuer.com', 'test_client_id')
    actual = jwt_verifier._construct_jwks_uri()
    expected = 'https://test_issuer.com/oauth2/v1/keys'
    assert actual == expected

    # issuer with '/' at the end
    jwt_verifier = JWTVerifier('https://test_issuer.com/', 'test_client_id')
    actual = jwt_verifier._construct_jwks_uri()
    expected = 'https://test_issuer.com/oauth2/v1/keys'
    assert actual == expected

    # issuer with /oauth2/ in URI
    jwt_verifier = JWTVerifier('https://test_issuer.com/oauth2/',
                               'test_client_id')
    actual = jwt_verifier._construct_jwks_uri()
    expected = 'https://test_issuer.com/oauth2/v1/keys'
    assert actual == expected


def test_get_jwk(mocker):
    # mock response
    jwks_resp = {'keys': [{'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid',
                           'use': 'sig', 'e': 'AQAB', 'n': 'test_n'},
                          {'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid2',
                           'use': 'sig', 'e': 'AQAB', 'n': 'test_n2'}]}
    request_executor = MockRequestExecutor
    request_executor.response = jwks_resp

    # check success flow
    jwt_verifier = JWTVerifier('https://test_issuer.com', 'test_client_id',
                               request_executor=request_executor)

    expected = {'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid',
                'use': 'sig', 'e': 'AQAB', 'n': 'test_n'}
    actual = jwt_verifier.get_jwk('test_kid')
    assert actual == expected

    # check if exception raised in case no matching key
    jwt_verifier._clear_requests_cache = mocker.Mock()
    with pytest.raises(JWKException):
        actual = jwt_verifier.get_jwk('test_kid_no_match')


def test_get_jwks(mocker):
    # mock response
    jwks_resp = {'keys': [{'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid',
                           'use': 'sig', 'e': 'AQAB', 'n': 'test_n'}]}
    request_executor = MockRequestExecutor
    request_executor.response = jwks_resp

    jwt_verifier = JWTVerifier('https://test_issuer.com', 'test_client_id',
                               request_executor=request_executor)

    actual = jwt_verifier.get_jwks()
    assert actual == jwks_resp


def test_get_jwk_by_kid():
    jwt_verifier = JWTVerifier('https://test_issuer.com', 'test_client_id')
    jwks_resp = {'keys': [{'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid',
                           'use': 'sig', 'e': 'AQAB', 'n': 'test_n'},
                          {'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid2',
                           'use': 'sig', 'e': 'AQAB', 'n': 'test_n2'}]}
    expected = {'kty': 'RSA', 'alg': 'RS256', 'kid': 'test_kid',
                'use': 'sig', 'e': 'AQAB', 'n': 'test_n'}
    actual = jwt_verifier._get_jwk_by_kid(jwks_resp, 'test_kid')
    assert actual == expected
    actual = jwt_verifier._get_jwk_by_kid(jwks_resp, 'test_kid_no_match')
    expected = None
    assert actual == expected


def test_verify_signature(mocker):
    headers = {'alg': 'RS256', 'kid': 'test_kid'}
    claims = {'test_claim_name': 'test_claim_value'}
    signing_input = 'test_signing_input'
    signature = 'test_signature'
    mock_parse_token = lambda token: (headers, claims, signing_input, signature)
    mocker.patch('okta_jwt_verifier.jwt_utils.JWTUtils.parse_token', mock_parse_token)

    mock_sign_verifier = mocker.Mock()
    mocker.patch('okta_jwt_verifier.jwt_utils.jws._verify_signature',
                 mock_sign_verifier)

    token = 'test_token'
    jwk = 'test_jwk'
    jwt_verifier = JWTVerifier('https://test_issuer.com', 'test_client_id')
    jwt_verifier.verify_signature(token, jwk)
    mock_sign_verifier.assert_called_with(signing_input=signing_input,
                                          header=headers,
                                          signature=signature,
                                          key=jwk,
                                          algorithms=['RS256'])


def test_verify_client_id():
    """Check if method verify_client_id works correctly."""
    # verify when aud is a string
    client_id = 'test_client_id'
    aud = client_id
    jwt_verifier = JWTVerifier('https://test_issuer.com', client_id)
    jwt_verifier.verify_client_id(aud)

    # verify when aud is an array
    aud = ['test_audience', client_id]
    jwt_verifier.verify_client_id(aud)

    # verify exception is raised when aud is a string
    with pytest.raises(JWTValidationException):
        aud = 'bad_aud'
        jwt_verifier.verify_client_id(aud)

    # verify exception is raised when aud is an array
    with pytest.raises(JWTValidationException):
        aud = ['bad_aud']
        jwt_verifier.verify_client_id(aud)

    # verify exception is raised when aud is not a string or array
    with pytest.raises(JWTValidationException):
        aud = {'aud': 'bad_aud'}
        jwt_verifier.verify_client_id(aud)


def test_verify_claims():
    """Check if method verify_claims works correctly."""
    client_id = 'test_client_id'
    audience = 'api://default'
    issuer = 'https://test_issuer.com'
    iss_time = time.time()

    claims = {'ver': 1,
              'jti': 'test_jti_str',
              'iss': issuer,
              'aud': audience,
              'iat': iss_time,
              'exp': iss_time+300,
              'cid': client_id,
              'uid': 'test_uid',
              'scp': ['openid'],
              'sub': 'test_jwt@okta.com'}
    # verify when aud is a string
    jwt_verifier = JWTVerifier(issuer, client_id)
    jwt_verifier.verify_claims(claims, ('iss', 'aud', 'exp'))


def test_verify_claims_invalid():
    """Check if method verify_claims raises an exception if any claim is invalid."""
    client_id = 'test_client_id'
    audience = 'api://default'
    issuer = 'https://test_issuer.com'
    iss_time = time.time()

    claims = {'ver': 1,
              'jti': 'test_jti_str',
              'iss': 'https://invalid_issuer.com',
              'aud': audience,
              'iat': iss_time,
              'exp': iss_time+300,
              'cid': client_id,
              'uid': 'test_uid',
              'scp': ['openid'],
              'sub': 'test_jwt@okta.com'}
    # verify when aud is a string
    jwt_verifier = JWTVerifier(issuer, client_id)
    with pytest.raises(JWTClaimsError):
        jwt_verifier.verify_claims(claims, ('iss', 'aud', 'exp'))


def test_verify_claims_missing_claim():
    """Check if method verify_claims raises an exception if required claim is missing."""
    client_id = 'test_client_id'
    issuer = 'https://test_issuer.com'
    iss_time = time.time()

    claims = {'ver': 1,
              'jti': 'test_jti_str',
              'iss': issuer,
              'iat': iss_time,
              'exp': iss_time+300,
              'cid': client_id,
              'uid': 'test_uid',
              'scp': ['openid'],
              'sub': 'test_jwt@okta.com'}
    # verify when aud is a string
    jwt_verifier = JWTVerifier(issuer, client_id)
    with pytest.raises(JWTValidationException):
        jwt_verifier.verify_claims(claims, ('iss', 'aud', 'exp'))


def test_access_token_verifier(monkeypatch, mocker):
    """Verify AccessTokenVerifier calls correct method of JWTVerifier with correct parameters."""
    class AsyncMock(mocker.MagicMock):
        def __call__(self, *args, **kwargs):
            return super().__call__(self, *args, **kwargs)

    mock_verify_access_token = AsyncMock()
    monkeypatch.setattr(JWTVerifier, 'verify_access_token', mock_verify_access_token)
    issuer = 'https://test_issuer.com'
    jwt_verifier = AccessTokenVerifier(issuer)
    jwt_verifier.verify('test_token')
    mock_verify_access_token.assert_called_with(mock_verify_access_token, 'test_token', ('iss', 'aud', 'exp'))


def test_id_token_verifier(monkeypatch, mocker):
    """Verify IDTokenVerifier calls correct method of JWTVerifier with correct parameters."""
    class AsyncMock(mocker.MagicMock):
        def __call__(self, *args, **kwargs):
            return super().__call__(self, *args, **kwargs)

    mock_verify_id_token = AsyncMock()
    monkeypatch.setattr(JWTVerifier, 'verify_id_token', mock_verify_id_token)
    issuer = 'https://test_issuer.com'
    client_id = 'test_client_id'
    jwt_verifier = IDTokenVerifier(issuer, client_id)
    jwt_verifier.verify('test_token')
    mock_verify_id_token.assert_called_with(mock_verify_id_token, 'test_token', ('iss', 'exp'), None)
