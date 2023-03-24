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
        $('#hide-shared-control').parent().addClass('d-none');
        $('#show-shared-control').parent().removeClass('d-none');
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
    })

    $('#show-shared-control').click(function() {
        $('li.transcription').css('background-color', '');
        $('#ms-col-1 li.transcription').each(function() {
            var targetForm = $( this ).attr('formula');
            $('li[formula="' + targetForm + '"]').addClass('work-cell bg-color-4 show-bg-color');
        })
        $( this ).parent().addClass('d-none');
        $('#hide-shared-control').parent().removeClass('d-none');
    })

    $('#hide-shared-control').click(function() {
        $('li.transcription').css('background-color', '');
        $('#ms-col-1 li.transcription').each(function() {
            var targetForm = $( this ).attr('formula');
            $('li[formula="' + targetForm + '"]').removeClass('work-cell bg-color-4 show-bg-color');
        })
        $( this ).parent().addClass('d-none');
        $('#show-shared-control').parent().removeClass('d-none');
    })

})
