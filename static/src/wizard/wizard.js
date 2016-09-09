angular.module('wizard', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/connect-orcid', {
            templateUrl: "wizard/connect-orcid.tpl.html",
            controller: "ConnectOrcidPageCtrl",
            resolve: {
                redirect: function(CurrentUser){
                    return CurrentUser.sendToCorrectPage(true)
                }
            }
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/confirm-publications', {
            templateUrl: "wizard/confirm-publications.tpl.html",
            controller: "ConfirmPublicationsCtrl",
            resolve: {
                redirect: function(CurrentUser){
                    return CurrentUser.sendToCorrectPage(true)
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/add-publications', {
            templateUrl: "wizard/add-publications.tpl.html",
            controller: "AddPublicationsCtrl",
            resolve: {
                redirect: function(CurrentUser){
                    return CurrentUser.sendToCorrectPage(true)
                }
            }
        })
    })



    .controller("ConnectOrcidPageCtrl", function($scope, $location, $http, $auth){


        //if ($auth.getPayload().orcid_id){
        //    console.log("we've got their ORCID already")
        //    if ($auth.getPayload().num_products){
        //        console.log("they are all set, redirecting to their profile")
        //        $location.url("u/" + $auth.getPayload().orcid_id)
        //    }
        //    else {
        //        console.log("no products! redirecting to add-products")
        //        $location.url("wizard/add-products")
        //    }
        //}




        console.log("WelcomePageCtrl is running!")
        $scope.hasOrcid = null
        $scope.doYouHaveAnOrcid = function(answer){
            console.log("setting doYouHaveAnOrcid", answer)
            $scope.hasOrcid = answer
        }
    })



    .controller("ConfirmPublicationsCtrl", function($scope, $location, $http, $auth, CurrentUser){
        console.log("ConfirmPublicationsCtrl is running!")

        // todo add this to the template.
        $scope.confirm = function(){
            CurrentUser.setProperty("finished_wizard", true).then(
                function(x, y, z){
                    console.log("finished setting finished_wizard", x, y, z)
                    $location.url("u/" + $auth.getPayload().orcid_id) // replace with CurrentUser method
                }
            )
        }

        $scope.finishProfile = function(){
            console.log("finishProfile()")
            $scope.actionSelected = "finish-profile"
            $http.post("api/me", {})
                .success(function(resp){
                    console.log("successfully refreshed everything, redirecting to profile page ", resp)
                    $auth.setToken(resp.token)

                    // todo this might should be a method on CurrentUser
                    $location.path("u/" + $auth.getPayload().orcid_id)
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










