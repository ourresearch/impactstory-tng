angular.module('group', [
])
    .factory("Group", function($http, $location, $route, $rootScope){
        var isLoading = false
        function getPersons(persons, achievements){
            var url = "/api/group/"
            $rootScope.progressbar.start()
            isLoading = true

            var params = {'persons': persons, 'achievements': achievements}
            return $http.get(url, { params:params }).then( function(resp){
                    $rootScope.progressbar.complete()
                    isLoading = false
                    return resp.data

                }, function(resp){
                    $rootScope.progressbar.complete()
                    isLoading = false
                    $location.url('page-not-found')
                })
        }


        return {
            getPersons: getPersons,
            badgesToShow: function(badges){
                return _.filter(badges, function(badge){
                    return !!badge.show_in_ui
                })
            },
            isLoading: isLoading
        }
    })