// Determine whether the <CTRL> key is being held down during the click
$(document).keydown(function(event){
    if(event.which=="17")
        cntrlIsPressed = true;
});

$(document).keyup(function(){
    cntrlIsPressed = false;
});

var cntrlIsPressed = false;

var colorPalette = ["#dddd22ff", "#d76a03ff", "#9ae5e6ff", "#659157ff", "#3f88c5ff"];

var count = 0;


$(function() {
    $('.card.search-hit').click(function() {
        if (cntrlIsPressed == false) {
            count = 0;
        }
        var target = $(this);
        var scrollContent = target[0].parentNode;
        var listElement = scrollContent.parentNode;
        var list = listElement.parentNode;
        for (i = 0; i < list.children.length; i++) {
            var list_of_list = list.children[i].children[1].children
            for(j = 0; j < list_of_list.length; j++){
                if(list_of_list[j].children[0].innerText == target[0].childNodes[1].innerText){
                    var scrollParent = list_of_list[j].parentNode.parentNode;
                    scrollParent.scrollTop = list_of_list[j].offsetTop - (($(window).height() / 2) - (scrollParent.children[0].offsetHeight / 2));
                    list_of_list[j].style.backgroundColor = colorPalette[count % colorPalette.length];
                } else {
                    if (cntrlIsPressed == false) {
                        list_of_list[j].style.backgroundColor = "#FFF"
                    }
                }
            }
        }
        count++;
    })
})
