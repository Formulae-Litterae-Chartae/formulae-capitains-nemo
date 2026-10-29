#
# This is an example VCL file for Varnish.
#
# It does not do anything by default, delegating control to the
# builtin VCL. The builtin VCL is called when there is no explicit
# return statement.
#
# See the VCL chapters in the Users Guide at https://www.varnish-cache.org/docs/
# and https://www.varnish-cache.org/trac/wiki/VCLExamples for more examples.

# Marker to tell the VCL compiler that this VCL has been adapted to the
# new 4.0 format.
vcl 4.0;

# Default backend definition. This points to the gunicorn server.
backend default {
    .host = "127.0.0.1";
    .port = "8000";
}

sub vcl_recv {
    # Happens before we check if we have this in cache already.
    #
    # Typically you clean up the request here, removing cookies you don't need,
    # rewriting the request, etc.

    # remove the Matomo tracking cookie
    if (req.url ~ "urn:cts:formulae:pancarte_noir_internal") {
        return (synth(404, "Denied by request filtering configuration"));
    }
    if (req.http.user-agent ~ "Bot") {
        if (req.url ~ "\+" || req.url ~ "%2B") {
            return (synth(404, "Denied by request filtering configuration"));
        }
        return (pass);
    }
    if (req.http.user-agent ~ "bot") {
        if (req.url ~ "\+" || req.url ~ "%2B") {
            return (synth(404, "Denied by request filtering configuration"));
        }
        return (pass);
    }
    if (req.http.user-agent ~ "Bytespider") {
        if (req.url ~ "\+" || req.url ~ "%2B") {
            return (synth(404, "Denied by request filtering configuration"));
        }
        return (pass);
    }
    if (req.http.referer ~ "google") {
        if (req.url ~ "\+" || req.url ~ "%2B") {
            return (synth(404, "Denied by request filtering configuration"));
        }
        return (pass);
    }
    if (req.url ~ "/texts/") {
        #if (req.url ~ "\+.*\+.*") {
        #    return (synth(404, "Denied by request filtering configuration"));
        #}
        return (pass);
    }
    set req.http.Cookie = regsuball(req.http.Cookie, "(^|;\s*)(_[_a-z0-9\.]+)=[^;]*", "");
    set req.http.Cookie = regsub(req.http.Cookie, "^;\s*", "");
    # save the cookies before the built-in vcl_recv (allows caching of pages with cookies)
    set req.http.Cookie-Backup = req.http.Cookie;
    unset req.http.Cookie;
    # To deal with the Authorization header I should probably do the same thing I did with the Cookie header above
    # I.e., put is in an Authorization-Backup header, then restore this to the Authorization header in vcl_hash
    # I will then need to get the backend to send a Vary header that says the response should be varied according to Authorization
    # See https://stackoverflow.com/questions/35119283/best-pratice-for-varnish-cache-content-with-authorization-header for some guidance
}

sub vcl_backend_response {
    # Happens after we have read the response headers from the backend.
    #
    # Here you clean the response headers, removing silly Set-Cookie headers
    # and other mistakes your backend does.

    # I think I should move the Set-Cookie header into a temporary header and then reset it again in vcl_deliver
    #set beresp.http.Set-Cookie-Backup = beresp.http.Set-Cookie;
    #unset beresp.http.Set-Cookie;
}

sub vcl_deliver {
    # Happens when we have all the pieces we need, and are about to send the
    # response to the client.
    #
    # You can do accounting or modifying the final object here.
    
    # Reset the Set-Cookie header
    #set resp.http.Set-Cookie = resp.http.Set-Cookie-Backup;
    #unset resp.http.Set-Cookie-Backup;
}

sub vcl_hash {
    if (req.http.Cookie-Backup) {
        # restore the cookies before the lookup if any. This should allow auth cookies to affect results
        # may need to add an HTTP Vary header on the backend to send either project or non-project pages
        set req.http.Cookie = req.http.Cookie-Backup;
        unset req.http.Cookie-Backup;
    }
}
