"""Cookie import from system browser."""



from http.cookiejar import Cookie



from woolworths_adapter import cookie_import





def test_cookie_to_json():

    c = Cookie(

        version=0,

        name="session",

        value="abc",

        port=None,

        port_specified=False,

        domain=".woolworths.co.nz",

        domain_specified=True,

        domain_initial_dot=True,

        path="/",

        path_specified=True,

        secure=True,

        expires=9999999999,

        discard=False,

        comment=None,

        comment_url=None,

        rest={},

        rfc2109=False,

    )

    data = cookie_import._cookie_to_json(c)

    assert data["name"] == "session"

    assert data["domain"] == ".woolworths.co.nz"


