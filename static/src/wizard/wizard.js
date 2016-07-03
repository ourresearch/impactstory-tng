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
                    console.log("we tried to refresh profile, but somethign went wrong :(", resp)
                    $scope.actionSelected = null
                })
        }
    })

    .controller("AddPublicationsCtrl", function($scope, $location, $http, $auth){
        console.log("AddPublicationsCtrl is running!")
    })










