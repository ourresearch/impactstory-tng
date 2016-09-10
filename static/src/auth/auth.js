console.log("loading")
angular.module('auth', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/oauth/:intent/:identityProvider', {
            templateUrl: "auth/oauth.tpl.html",
            controller: "OauthCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "auth/login.tpl.html",
            controller: "LoginCtrl"
        })
    })


    .controller("LoginCtrl", function($scope, CurrentUser, $location, $http, $auth){
        console.log("LoginCtrl is running!")
        $scope.currentUser = CurrentUser






    })

    .controller("OauthCtrl", function($scope, $cookies, $routeParams, $location, $http, CurrentUser){
        var requestObj = $location.search()
        if (_.isEmpty(requestObj)){
            console.log("we didn't get any codes or verifiers in the URL. aborting.")
            $location.url("/")
            return false
        }
        var absUrl = $location.absUrl()
        requestObj.redirectUri = absUrl.split("?")[0] // remove the search part of URL
        console.log("using this redirectUri", requestObj.redirectUri)

        // track signups that started at the opencon landing page
        if ($cookies.get("sawOpenconLandingPage")) {
            requestObj.sawOpenconLandingPage = true
        }

        var urlBase = "api/me/"
        var url = urlBase + $routeParams.identityProvider + "/" + $routeParams.intent

        console.log("sending this up to the server", requestObj)
        $http.post(url, requestObj)
            .success(function(resp){
                console.log("we successfully called am api/me endpoint. got this back:", resp)
                CurrentUser.setFromToken(resp.token)
                CurrentUser.sendHome()

            })
            .error(function(resp){
              console.log("problem getting token back from server!", resp)
                // todo tell the user what went wrong
            })

    })










