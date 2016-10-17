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


    .controller("LoginCtrl", function($scope, CurrentUser, $location, $http){
        console.log("LoginCtrl is running!")
        $scope.currentUser = CurrentUser
        $scope.global.showBottomStuff = false
        $scope.global.hideHeader = true
        $scope.global.isFocusPage = true






    })

    .controller("OauthCtrl", function($scope, $cookies, $routeParams, $location, $http, $mdToast, CurrentUser){
        $scope.global.showBottomStuff = false
        $scope.global.hideHeader = true
        $scope.global.isFocusPage = true


        var requestObj = $location.search()
        if (_.isEmpty(requestObj)){
            console.log("we didn't get any codes or verifiers in the URL. aborting.")
            $location.url("/")
            return false
        }

        // set scope vars
        $scope.identityProvider = $routeParams.identityProvider
        $scope.intent = $routeParams.intent
        $scope.global.showBottomStuff = false



        var absUrl = $location.absUrl()
        requestObj.redirectUri = absUrl.split("?")[0] // remove the search part of URL
        console.log("using this redirectUri", requestObj.redirectUri)

        // track signups that started at the opencon landing page
        // this is ignored by server unless we are hitting /me/twitter/register
        requestObj.customLandingPage = $cookies.put("customLandingPage")

        var urlBase = "api/me/"
        var url = urlBase + $routeParams.identityProvider + "/" + $routeParams.intent


        // temp hack
        if ($routeParams.identityProvider == "twitter" && $routeParams.intent == "connect"){
            var msg = "Your Twitter account is connected!"
        }




        console.log("sending this up to the server", requestObj)
        $http.post(url, requestObj)
            .success(function(resp){
                console.log("we successfully called am api/me endpoint. got this back:", resp)
                CurrentUser.setFromToken(resp.token)
                CurrentUser.sendHome()
                if (msg){
                    $mdToast.show(
                        $mdToast.simple()
                            .textContent(msg)
                            .position("top")
                    )
                }

            })
            .error(function(error, status){
                console.log("the server returned an error", status, error)
                if (status == 404) {
                    $scope.error = "not-found"
                    $scope.identityProviderId = error.identity_provider_id
                }

            })

    })










