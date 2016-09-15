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

                    return CurrentUser.sendHomePromise(true)
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
                    return CurrentUser.sendHomePromise(true)
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/add-publications', {
            templateUrl: "wizard/add-publications.tpl.html",
            controller: "AddPublicationsCtrl"

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
            console.log("finishProfile()")
            $scope.actionSelected = "finish-profile"

            CurrentUser.setProperty("finished_wizard", true).then(
                function(x){
                    console.log("finished setting finished_wizard", x)
                }
            )

            // this runs concurrently with the call to the server to set finished_wizard just above.
            $http.post("api/me/refresh", {})
                .success(function(resp){
                    console.log("successfully refreshed everything ")
                    CurrentUser.setFromToken(resp.token)
                    CurrentUser.sendHome()

                })
                .error(function(resp){
                    console.log("we tried to refresh profile, but something went wrong :(", resp)
                    $scope.actionSelected = null
                })

        }
    })

    .controller("AddPublicationsCtrl", function($scope, $location, $http, $auth, CurrentUser){
        console.log("AddPublicationsCtrl is running!")

        $scope.state = "prompting"
        function checkForNewProducts(){
            $scope.state = "polling"
            console.log("checking for new products")
            $http.post("api/me/orcid/refresh", {}).success(function(resp){
                console.log("got stuff back from api/me/orcid")
                var oldNumberOfProducts = CurrentUser.d.num_products
                CurrentUser.setFromToken(resp.token)
                console.log("used to have " + oldNumberOfProducts + " products, now " + CurrentUser.d.num_products)


                if (oldNumberOfProducts != CurrentUser.d.num_products){
                    console.log("found the new products! assuming we're done getting products now.")
                    $scope.state = "making-profile"
                    $scope.num_products_added = CurrentUser.d.num_products - oldNumberOfProducts

                    // profile has all products now, but we need to get metrics. refresh it.
                    $http.post("api/me/refresh", {})
                        .success(function(resp){
                            console.log("successfully refreshed everything ")
                            CurrentUser.setFromToken(resp.token)

                            // have save that the wizard is done before sending home.
                            // this is three callbacks deep at this point, so good to refactor by
                            // chaining promises later.
                            CurrentUser.setProperty("finished_wizard", true).then(
                                function(x){
                                    console.log("finished setting finished_wizard", x)
                                    CurrentUser.sendHome()
                                }
                            )

                        })
                        .error(function(resp){
                            console.log("we tried to refresh profile, but something went wrong :(", resp)
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










