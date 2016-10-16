angular.module('person', [
])



    .factory("Person", function($http, $q, $route, $rootScope, CurrentUser){

        var data = {}
        var isLoading = false
        var badgeSortLevel = {
            "gold": 1,
            "silver": 2,
            "bronze": 3
        }
        var beltDescriptions = {
            white: "initial",
            yellow: "promising",
            orange: "notable",
            brown: "extensive",
            black: "exceptional"
        }

        function load(orcidId, force){
            console.log("loading the Person")


            // if the data for this profile is already loaded, just return it
            // unless we've been told to force a refresh from the server.
            if (data.orcid_id == orcidId && !force){
                console.log("Person Service getting from cache:", orcidId)
                return $q.when(data)
            }


            var url = "/api/person/" + orcidId
            console.log("Person Service getting from server:", orcidId)
            $rootScope.progressbar.start()
            isLoading = true
            return $http.get(url)
                .success(function(resp){

                    // clear the data object and put the new data in
                    for (var member in data) delete data[member];
                    overwriteData(resp)
                    $rootScope.progressbar.complete()
                    isLoading = false

                })
                .error(function(resp){
                    $rootScope.progressbar.complete()
                    isLoading = false

                })
        }

        function overwriteData(newData){
            // put the response in the data object
            _.each(newData, function(v, k){
                data[k] = v
            })

            // add computed properties

            // total posts
            var postCounts = _.pluck(data.sources, "posts_count")
            data.numPosts = postCounts.reduce(function(a, b){return a + b}, 0)

            // date of earliest publication
            var earliestPubYear = _.min(_.pluck(data.products, "year"))
            if (earliestPubYear > 0 && earliestPubYear <= 2015) {
                data.publishingAge = 2016 - earliestPubYear
            }
            else {
                data.publishingAge = 1
            }
        }

        function setFulltextUrl(productId, fulltextUrl) {
            _.each(data.products, function(myProduct){
                if (myProduct.id == productId){
                    myProduct.fulltext_url = fulltextUrl
                }
            });
            var apiUrl = "/api/person/" + data.orcid_id
            var postBody = {
                product: {
                    id: productId,
                    fulltext_url: fulltextUrl
                }
            }

            $http.post(apiUrl, postBody)
                .success(function(resp){
                    console.log("we set the fulltext url!", resp)
                    overwriteData(resp)

                    // todo: figure out if we actually need this
                    $route.reload()
                })
                .error(function(resp){
                    console.log("we failed to set the fulltext url", resp)
                    $route.reload()
                })

        }


        function getBadgesWithConfigs(configDict) {
            var ret = []
            _.each(data.badges, function(myBadge){
                var badgeDef = configDict[myBadge.name]
                var enrichedBadge = _.extend(myBadge, badgeDef)
                enrichedBadge.sortLevel = badgeSortLevel[enrichedBadge.level]
                ret.push(enrichedBadge)
            })

            return ret
        }

        function belongsToCurrentUser(){
            if (!CurrentUser.isLoggedIn()) {
                return false
            }
            return CurrentUser.d.id == data.id
        }


        return {
            d: data,
            load: load,
            badgesToShow: function(){
                return _.filter(data.badges, function(badge){
                    return !!badge.show_in_ui
                })
            },
            getBadgesWithConfigs: getBadgesWithConfigs,
            setFulltextUrl: setFulltextUrl,
            reload: function(){
                return load(data.orcid_id, true)
            },
            clear:function(){
                for (var member in data) delete data[member];
            },
            belongsToCurrentUser: belongsToCurrentUser,
            isLoading: function(){
                return !!isLoading
            }
        }
    })