angular.module('currentUser', [
])



    .factory("CurrentUser", function($auth,
                                     $http,
                                     $rootScope,
                                     $q,
                                     $route,
                                     $location,
                                     $mdToast,
                                     $cookies,
                                     $timeout){
        
        var data = {}
        var isLoading = false
        var sendToIntercom = function(){
            // this is slow, but that's ok since it's async and doesn't affect the UX
            // only call it if they have an orcid_id since the call needs it
            if (data.orcid_id) {
                $http.get("api/person/" + data.orcid_id).success(function(resp) {
                    bootIntercom(resp)
                })
            }
        }

        var isAuthenticatedPromise = function(){
            // this is actually a synchronous method, it just returns
            //      a promise so it can be used in route definitions.
            var deferred = $q.defer()
            if ($auth.isAuthenticated()) {
                deferred.resolve()
            }
            else {
                console.log("user isn't logged in, so isAuthenticatedPromise() is rejecting promise.")
                deferred.reject()
            }
            return deferred.promise
        }



        var twitterAuthenticate = function (intent) {
            // send the user to twitter.com to authenticate
            // twitter will send them back to us from there.
            // @intent should be either "register" or "login".

            var redirectUri = window.location.origin + "/oauth/" + intent + "/twitter"

            console.log("authenticate with twitters!");

            // first ask our server to get the OAuth token that we use to create the
            // twitter URL that we will redirect the user too.

            $rootScope.progressbar.start() // it will take some time

            var baseUrlToGetOauthTokenFromOurServer = "/api/auth/twitter/request-token?redirectUri=";
            var baseTwitterLoginPageUrl = "https://api.twitter.com/oauth/authenticate?oauth_token="
            $http.get(baseUrlToGetOauthTokenFromOurServer + redirectUri).success(
                function(resp){
                    console.log("twitter request token", resp)
                    var twitterLoginPageUrl = baseTwitterLoginPageUrl + resp.oauth_token
                    window.location = twitterLoginPageUrl
                }
            )
        };

        var orcidAuthenticate = function (intent, orcidAlreadyExists) {
            // send the user to orcid.org to authenticate
            // orcid will send them back to us from there.
            // @intent should be either "register" or "login".
            // @orcidAlreadyExists (bool) lets us know whether to send you to
            //      the ORCID login screen or signup screen.

            var redirectUri = window.location.origin + "/oauth/" + intent + "/orcid"

            console.log("ORCID authenticate!", intent, orcidAlreadyExists)

            var authUrl = "https://orcid.org/oauth/authorize" +
                "?client_id=APP-PF0PDMP7P297AU8S" +
                "&response_type=code" +
                "&scope=/authenticate" +
                "&redirect_uri=" + redirectUri

            if (orcidAlreadyExists){
                authUrl += "&show_login=true"
            }

            window.location = authUrl
            return true
        }

        function disconnectTwitter(){

            isLoading = true
            console.log("disconnect twitter!")
            $mdToast.show(
                $mdToast.simple()
                    .textContent("Disconnecting Twitter...")
                    .position("top")
                    .hideDelay(5000)
            )

            return $http.post("api/me/twitter/disconnect", {})
                .success(function(resp){
                    isLoading = false
                    $mdToast.show(
                        $mdToast.simple()
                            .textContent("Done!")
                            .position("top")
                    )
                    setFromToken(resp.token)
                })
        }

        function sendHome(){
            console.log("calling sendToCorrectPage() with this data", data)
            var url
            var currentPath = $location.path()
            console.log("currentPath", currentPath)


            if (data.finished_wizard && isMyProfile(currentPath)){
                url = currentPath
            }

            else if (data.finished_wizard){
                url = "/u/" + data.orcid_id
            }

            else if (data.num_products > 0){
                url = "/wizard/confirm-publications"
            }

            else if (data.orcid_id){
                url = "/wizard/add-publications"
            }

            else {
                url = "/wizard/connect-orcid"
            }

            if (currentPath == url ){
                return false
            }
            else {
                $location.url(url)
                return true
            }
        }

        function isMyProfile(url){
            if (!data.orcid_id){
                return false
            }
            return url.indexOf(data.orcid_id) > -1
        }




        function sendHomePromise(requireLogin){
            var deferred = $q.defer()

            if (!isLoggedIn()){
                if (requireLogin){
                    $location.url("login")
                }
                else {
                    deferred.resolve()
                }
            }

            else {
                var redirecting = sendHome()

                console.log("sendHomePromise redirceing=", redirecting)

                if (!redirecting){
                    deferred.resolve()
                }
            }

            return deferred.promise
        }


        function isLoggedIn(returnPromise){
            if (returnPromise){
                var deferred = $q.defer()
                if ($auth.isAuthenticated()) {
                    deferred.resolve()
                }
                else {
                    deferred.reject()
                }
                return deferred.promise
            }


            return $auth.isAuthenticated()
        }

        function setProperty(k, v){
            var data = {}
            data[k] = v
            return $http.post("api/me", data)
                .success(function(resp){
                    setFromToken(resp.token)
                })
                .error(function(resp){
                    console.log("we tried to set a thing, but it didn't work", data, resp)
                })
        }


        function logout(){
            $auth.logout()
            _.each(data, function(v, k){
                delete data[k]
            })
            Intercom('shutdown')
            return true
        }

        function boot(){
            _.each($auth.getPayload(), function(v, k){
                data[k] = v
            })
            return reloadFromServer()
        }

        function reloadFromServer(){
            console.log("reloading from server")
            if (!isLoggedIn()){
                console.log("user is not logged in")
                return false
            }

            $http.get("api/me").success(function(resp){
                console.log("refreshing data in CurrentUser", resp)
                setFromToken(resp.token)
            })
        }
        
        function bootIntercom(person){
            var percentOA = person.percent_fulltext
            if (percentOA === null) {
                percentOA = undefined
            }
            else {
                percentOA * 100
            }
    
            var intercomInfo = {
                // basic user metadata
                app_id: "z93rnxrs",
                name: person._full_name,
                user_id: person.orcid_id, // orcid ID
                claimed_at: moment(person.claimed_at).unix(),
                email: person.email,
    
                // user stuff for analytics
                percent_oa: percentOA,
                num_posts: person.num_posts,
                num_mentions: person.num_mentions,
                num_products: person.products.length,
                num_badges: person.badges.length,
                num_twitter_followers: person.num_twitter_followers,
                campaign: person.campaign,
                fresh_orcid: person.fresh_orcid,
    
                // we don't send person responses for deleted users (just 404s).
                // so if we have a person response, this user isn't deleted.
                // useful for when users deleted profile, then re-created later.
                is_deleted: false
    
            }
    
            if ($cookies.get("sawOpenconLandingPage")) {
                intercomInfo.saw_opencon_landing_page = true

            }
    
            console.log("sending to intercom", intercomInfo)
            window.Intercom("boot", intercomInfo)
        } 

        function setFromToken(token){
            $auth.setToken(token) // synchronous
            _.each($auth.getPayload(), function(v, k){
                data[k] = v
            })

            sendToIntercom()
        }

        return {
            isAuthenticatedPromise: isAuthenticatedPromise,
            twitterAuthenticate: twitterAuthenticate,
            orcidAuthenticate: orcidAuthenticate,
            disconnectTwitter: disconnectTwitter,
            setFromToken: setFromToken,
            sendHome: sendHome,
            sendHomePromise: sendHomePromise,
            setProperty: setProperty,
            d: data,
            logout: logout,
            isLoggedIn: isLoggedIn,
            reloadFromServer: reloadFromServer,
            boot: boot,
            isMyProfile: isMyProfile,
            isLoading: function(){
                return !!isLoading
            }
        }
    })