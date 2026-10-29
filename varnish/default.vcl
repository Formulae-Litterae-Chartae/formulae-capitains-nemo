# Last modified: 2026-10-29 by Thorben
#
# Varnish in front of the Flask/gunicorn application.
# More information on traffic management can be found here: https://formulae-litterae-chartae.github.io/formulae-capitains-nemo/traffic-management.html
# Rules in vcl_recv, in order:
#   1. Requests for the internal collection get a 404.
#   2. Bots and visitors referred by Google get a 404 if the URL contains "+".
#      Single-page requests use the cache like any other visitor.
#   3. /auth/, /admin/ and /lang/ are never cached.
#   4. /texts/ is cached, except for visitors with a session cookie
#      and for combined passages (URLs containing "+").
#   5. Everything else is cached. Cookies starting with "_" (Matomo) are
#      removed so they do not split the cache.
vcl 4.0;

# gunicorn (Flask app). It must listen on 127.0.0.1 only,
# otherwise Varnish and all rules below can be bypassed via port 8000.
backend default {
        .host = "127.0.0.1";
        .port = "8000";
}

sub vcl_recv {
        # Never trust a client-supplied copy of our internal header (see rule 5).
        unset req.http.Cookie-Backup;

        # 1. Internal collection. Only the part without ":" is matched, so that
        #    percent-encoded variants (urn%3Acts%3A...) are blocked as well.
        if (req.url ~ "(?i)pancarte_noir_internal") {
                return (synth(404, "Denied by request filtering configuration"));
        }

        # 2. Bots, crawlers and visitors referred by Google.
        #    Long combined URLs ("+" or "%2B") are expensive, so they are refused.
        #    Single-page requests continue below and use the cache like any other visitor.
        if (req.http.User-Agent ~ "[Bb]ot|[Cc]rawl|[Ss]pider|[Ss]lurp|[Ss]crap|https?://" || !req.http.User-Agent || req.http.Referer ~ "google") {
                if (req.url ~ "(?i)\+|%2B") {
                        return (synth(404, "Denied by request filtering configuration"));
                }
        }

        # 3. Sensitive or state-changing pages are never cached.
        #    (The app also sends no-store for /auth/ and /lang/.)
        if (req.url ~ "^/(auth|admin|lang)/") {
                return (pass);
        }

        # 4. Texts
        if (req.url ~ "/texts/") {
                # Visitors with a session cookie (e.g. logged in) get their own
                # pages directly from the backend, so private copies do not fill the cache.
                if (req.http.Cookie ~ "(^|;\s*)session=") {
                        return (pass);
                }
                # Combined passages are rarely requested twice: don't waste cache space.
                if (req.url ~ "(?i)\+|%2B") {
                        return (pass);
                }
        }

        # 5. Cookie handling for cacheable requests.
        #    Remove cookies starting with "_" (Matomo: _pk_id.*, _pk_ses.*, ...).
        #    They never change the page, but would give every visitor an own cache variant.
        set req.http.Cookie = regsuball(req.http.Cookie, "(^|;\s*)(_[_a-z0-9\.]+)=[^;]*", "");
        set req.http.Cookie = regsub(req.http.Cookie, "^;\s*", "");

        # Hide the remaining cookies from the built-in vcl_recv, which passes every
        # request that carries a Cookie header. vcl_hash restores them.
        set req.http.Cookie-Backup = req.http.Cookie;
        unset req.http.Cookie;

        # Note: requests with an Authorization header are already passed by the
        # built-in vcl_recv. Nothing to do unless the app starts relying on it
        # for cacheable pages.
}

sub vcl_hash {
        # Restore the cookies hidden in vcl_recv. Cookies are not part of the hash.
        # The backend sends "Vary: Cookie", so Varnish keeps one cached variant per
        # cookie string (without the "_" cookies removed above).
        if (req.http.Cookie-Backup) {
                set req.http.Cookie = req.http.Cookie-Backup;
                unset req.http.Cookie-Backup;
        }
}

sub vcl_backend_response {
        # Serve a slightly stale page while a fresh copy is fetched, so Flask does
        # not get a burst of requests when a popular object expires.
        set beresp.grace = 1h;
}


sub vcl_backend_error {
        # Called when Varnish gets no response from gunicorn (connection refused,
        # timeout, ...). Shows a friendly page instead of Varnish's default
        # "Guru Meditation" page. Pages that are still in the cache are served normally.
        set beresp.status = 503;
        set beresp.reason = "Service temporarily unavailable";
        set beresp.http.Content-Type = "text/html; charset=utf-8";
        set beresp.http.Retry-After = "300";

        # Keep the error page in the cache only briefly, so the site recovers
        # quickly once the backend is back.
        set beresp.ttl = 10s;

        synthetic({"<!doctype html>
                        <html lang='en'>
                                <head>
                                        <meta charset='utf-8'>
                                        <meta name='viewport' content='width=device-width, initial-scale=1'>
                                        <title>Service unavailable</title>
                                </head>
                                <body>
                                        <h1>Service unavailable</h1>
                                        <p>Sorry, this website is temporarily unavailable.</p>
                                        <p>Please consider using the instance operated by the Akademie der Wissenschaften Hamburg: <a href='https://formulae.awhamburg.de/'>formulae.awhamburg.de</a></p>
                                        <p>Please visit the project website for more information: <a href='https://www.formulae.uni-hamburg.de/'>formulae.uni-hamburg.de</a></p>
                                </body>
                        </html>
                "});

        # Do not run the built-in vcl_backend_error, which would replace this page.
        return (deliver);
}

sub vcl_deliver {
        # Debug header for testing (passes and misses both show MISS).
        # Remove it if you do not want to expose it.
        if (obj.hits > 0) {
                set resp.http.X-Cache = "HIT";
        } else {
                set resp.http.X-Cache = "MISS";
        }
}
