angular.module('wizard', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/welcome', {
            templateUrl: "wizard/welcome.tpl.html",
            controller: "WelcomePageCtrl",
            resolve: {
                isLoggedIn: function($rootScope){
                    return $rootScope.isAuthenticatedPromise()
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/orcid-connect', {
            templateUrl: "wizard/orcid-connect.tpl.html",
            controller: "OrcidConnectCtrl",
            resolve: {
                isLoggedIn: function($rootScope){
                    return $rootScope.isAuthenticatedPromise()
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/twitter-register', {
            templateUrl: "wizard/twitter-register.tpl.html",
            controller: "TwitterRegisterCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/my-publications', {
            templateUrl: "wizard/my-publications.tpl.html",
            controller: "MyPublicationsCtrl",
            resolve: {
                isLoggedIn: function($rootScope){
                    return $rootScope.isAuthenticatedPromise()
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/add-publications', {
            templateUrl: "wizard/add-publications.tpl.html",
            controller: "AddPublicationsCtrl",
            resolve: {
                isLoggedIn: function($rootScope){
                    return $rootScope.isAuthenticatedPromise()
                }
            }
        })
    })



    .controller("WelcomePageCtrl", function($scope, $location, $http, $auth){


        // @todo put this in the route def  so it's not ugly while it loads, or do a better profile-loading thingy
        if ($auth.getPayload().orcid_id){
            console.log("we've got their ORCID already")
            if ($auth.getPayload().num_products){
                console.log("they are all set, redirecting to their profile")
                $location.url("u/" + $auth.getPayload().orcid_id)
            }
            else {
                console.log("no products! redirecting to add-products")
                $location.url("wizard/add-products")
            }
        }


        console.log("WelcomePageCtrl is running!")
        $scope.hasOrcid = null
        $scope.doYouHaveAnOrcid = function(answer){
            console.log("setting doYouHaveAnOrcid", answer)
            $scope.hasOrcid = answer
        }

    })



    .controller("OrcidConnectCtrl", function($scope, $location, $http, $auth, $rootScope){
        console.log("OrcidConnectCtrl running")
        var searchObject = $location.search();
        var code = searchObject.code

        if (!code){
            console.log("there is no oauth code in the url. quitting.")
            $location.path("/")
            return false
        }

        var requestObj = {
            redirectUri: $rootScope.orcidRedirectUri.connect
        }

        console.log("POSTing the request code to the server", requestObj)
        $http.post("api/me/orcid/oauth_code/" + code, requestObj)
            .success(function(resp){
                console.log("we successfully added an ORCID!", resp)
                $auth.setToken(resp.token)
                if ($auth.getPayload().num_products > 0) {
                    console.log("they have some works, good! redirect to your-publications")
                    $location.url("wizard/my-publications")
                }
                else {
                    console.log("they have no works. redirect to page to add-publications")
                    $location.url("wizard/add-publications")

                }

                //$rootScope.sendCurrentUserToIntercom()
                //$location.url("u/" + payload.sub)
            })
            .error(function(resp){
              console.log("problem getting token back from server!", resp)
                //$location.url("/")
            })



    })



    .controller("TwitterRegisterCtrl", function($scope, $location, $http, $auth, $rootScope){
        console.log("TwitterRegisterCtrl running")


        var searchObject = $location.search();
        var token = searchObject.oauth_token
        var verifier = searchObject.oauth_verifier

        if (!token || !verifier){
            console.log("twitter didn't give oauth_verifier and a oauth_token")
            $location.url("/")
            return false
        }

        var requestObj = {
            token: token,
            verifier: verifier
        }

        $http.post("api/auth/register/twitter", requestObj)
            .success(function(resp){
                $auth.setToken(resp.token)
                if (resp.is_new_profile){
                    console.log("registered a new user with twitter", resp)
                    $location.url("wizard/welcome")
                    //$rootScope.sendCurrentUserToIntercom()
                }
                else {
                    console.log("an existing impactstory user logged in with twitter, using the register button", resp)
                    if ($auth.getPayload().orcid_id){
                        console.log("they've got a orcid in their profile. sending them to profile page.")
                        $location.url("u/" + $auth.getPayload().orcid_id)
                    }
                    else {
                        console.log("they are logged in with twitter, but no orcid yet.")
                        $location.url("wizard/welcome")
                    }
                }



            })
            .error(function(resp){
              //console.log("problem getting token back from server!", resp)
              //  $location.url("/")
            })





    })


    .controller("MyPublicationsCtrl", function($scope, $location, $http, $auth){
        console.log("MyPublicationsCtrl is running!")
        $scope.finishProfile = function(){
            console.log("finishProfile()")
            $scope.actionSelected = "finish-profile"
            $http.post("api/me", {})
                .success(function(resp){
                    console.log("successfully refreshed everything, redirecting to profile page ", resp)
                    $auth.setToken(resp.token)
                    $location.url("u/" + $auth.getPayload().orcid_id)
                })
                .error(function(resp){
                    console.log("we tried to refresh profile, but something went wrong :(", resp)
                    $scope.actionSelected = null
                })
        }
    })

    .controller("AddPublicationsCtrl", function($scope, $location, $http, $auth){
        console.log("AddPublicationsCtrl is running!")

        $scope.state = "prompting"
        function checkForNewProducts(){
            $scope.state = "polling"
            console.log("checking for new products")
            $http.post("api/me/orcid", {}).success(function(resp){
                console.log("got stuff back from api/me/orcid", resp)
                if (resp.num_products != $auth.getPayload().num_products){

                    console.log("found the new products! assuming we're done getting products now.")
                    $scope.state = "making-profile"
                    $scope.num_products_added = resp.num_products - $auth.getPayload().num_products
                    $auth.setToken(resp.token)

                    // profile has all products now, but we need to get metrics. refresh it.
                    $http.post("api/me", {}).success(function(resp){
                        console.log("successfully refreshed the profile. redirecting.")
                        $location.url("u/" + $auth.getPayload().orcid_id)
                    })
                }
                else {
                    // no change, let's keep checking.
                    return checkForNewProducts()
                }
            })
        }


        $scope.start = function(){
            console.log("start!")
            $scope.polling = true
            checkForNewProducts()
        }
    })










