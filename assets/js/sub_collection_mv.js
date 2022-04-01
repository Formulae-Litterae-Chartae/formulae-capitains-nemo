// Determine whether the <CTRL> key is being held down during the click
$(document).keydown(function(event){
    if(event.which=="17")
        cntrlIsPressed = true;
});

$(document).keyup(function(){
    cntrlIsPressed = false;
});

var cntrlIsPressed = false;

var colorPalette = ["#dddd22", "#9ae5e6", "#E2D5B6", "#CFDFCE", "#7CFC00", "#FFA347", "#B5E2DA", "F5B7F5", "#BEDF7C", "#00FFFF"];

var count = 0;
var oldColor = "#fff";
var newColor = "#dddd22";


$(function() {
    $('.card.search-hit.transcription').click(function() {
        console.log(count);
        var target = $(this);
        if (cntrlIsPressed == false) {
            count = 0;
            newColor = colorPalette[count % colorPalette.length];
            oldColor = '#fff';
        } else {
            if ( target.css('background-color') != "rgb(255, 255, 255)" ) {
                oldColor = target.css('background-color');
            } else {
                oldColor = '#fff';
            }
        }
        var formula = target.attr('formula');
        $('.card.search-hit.transcription').each(function() {
            if ( $(this).attr('formula') == formula ) {
                if ( oldColor != '#fff' ) {
                    $(this).css('background-color', "#fff");
                } else {
                    var scrollParent = $(this).parents('.card.mv-rows');
                    scrollParent.scrollTop($(this).offset().top - scrollParent.offset().top + scrollParent.scrollTop() - scrollParent.height()/2 + $(this).height()/2);
                    $(this).css('background-color', newColor);
                }
            } else {
                if (cntrlIsPressed == false) {
                    $(this).css('background-color', "#fff");
                }
            }
        
        })
        if ( oldColor == '#fff' ) {
            count++
            newColor = colorPalette[count % colorPalette.length];
        } else {
            newColor = oldColor;
            oldColor = '#fff';
        }
//         var scrollContent = target[0].parentNode;
//         var listElement = scrollContent.parentNode;
//         var list = listElement.parentNode;
//         for (i = 0; i < list.children.length; i++) {
//             var list_of_list = list.children[i].children[1].children
//             for(j = 0; j < list_of_list.length; j++){
//                 if(list_of_list[j].children[0].innerText == target[0].childNodes[1].innerText){
//                     var scrollParent = list_of_list[j].parentNode.parentNode;
//                     scrollParent.scrollTop = list_of_list[j].offsetTop - (($(window).height() / 2) - (scrollParent.children[0].offsetHeight / 2));
//                     list_of_list[j].style.backgroundColor = colorPalette[count % colorPalette.length];
//                 } else {
//                     if (cntrlIsPressed == false) {
//                         list_of_list[j].style.backgroundColor = "#FFF"
//                     }
//                 }
//             }
//         }
//         count++;
    })
})
