angular.module('group', [
])
    .factory("Group", function($http, $q, $route, $rootScope){
        var isLoading = false
        function getPersons(persons){
            var url = "/api/group/"
            $rootScope.progressbar.start()
            isLoading = true

            var params = {'persons': persons}
            return $http.get(url, { params:params }).then( function(resp){
                    $rootScope.progressbar.complete()
                    isLoading = false

                    return resp.data

                }, function(resp){
                    $rootScope.progressbar.complete()
                    isLoading = false
                    $q.defer().reject()
                })
        }


        return {
            getPersons: getPersons,
            isLoading: isLoading
        }
    })