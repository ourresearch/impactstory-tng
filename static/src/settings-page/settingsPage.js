angular.module('settingsPage', [
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/me/settings', {
            templateUrl: 'settings-page/settings-page.tpl.html',
            controller: 'settingsPageCtrl',
            resolve: {
                isAuth: function($q, CurrentUser){
                    return CurrentUser.isLoggedIn(true)
                }
            }
        })
    })



    .controller("settingsPageCtrl", function($scope,
                                             $rootScope,
                                             $auth,
                                             $route,
                                             $location,
                                             $http,
                                             Person,
                                             CurrentUser){

        console.log("the settings page loaded")
        var myOrcidId = CurrentUser.d.orcid_id
        $scope.orcidId = myOrcidId
        $scope.givenNames = CurrentUser.d.given_names
        $scope.currentUser = CurrentUser


        // launching for the DORA anniv in december :)
        $scope.dorafied = null
        //$http.get("api/me")
        //    .success(function(resp){
        //        console.log("got stuff back from /me", resp)
        //        if (resp.promos.dorafy){
        //            $scope.dorafied = true
        //        }
        //    })




        $scope.wantToDelete = false
        $scope.deleteProfile = function() {
            $http.delete("/api/me")
                .success(function(resp){
                    // let Intercom know
                    window.Intercom("update", {
                        user_id: myOrcidId,
                        is_deleted: true
                    })

                    CurrentUser.logout()
                    $location.path("/")
                    alert("Your profile has been deleted.")
                })
                .error(function(){
                    alert("Sorry, something went wrong!")
                })
        }


        $scope.syncState = 'ready'

        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.syncState = "working"
            $http.post("/api/me/refresh")
                .success(function(resp){
                    CurrentUser.setFromToken(resp.token)

                    // force a reload of the person
                    Intercom('trackEvent', 'synced-to-edit');
                    Person.load(myOrcidId, true).then(
                        function(resp){
                            $scope.syncState = "success"
                            console.log("we reloaded the Person after sync")
                        }
                    )
                })
        }

        $scope.setDorafy = function(dorafy){
            console.log("dorafy!", dorafy)
            $scope.doraState = 'working'
            var postData = {
                dorafy: true
            }
            $http.post("api/me/promos", postData)
                .success(function(resp){
                    $scope.doraState = 'done'
                    console.log("set the dorafy!", resp)
                })
        }

    })












