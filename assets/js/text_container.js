
    $(document).ready(function() {

        $('#sidebarCollapse_l').click(function() {
            $('#sidebar_l').toggleClass('active');
            var el_l = document.getElementById('sidebarCollapse_l');
            if ($('#sidebar_l').css('marginLeft')=='0px'){
                el_l.textContent = '«';
                el_l.setAttribute('title', 'Linke Spalte zuklappen.');
            }else{
                el_l.textContent = '»';
                el_l.setAttribute('title', 'Linke Spalte aufklappen.');
            }
        });

        $('#sidebarCollapse_r').click(function() {
            $('#sidebar_r').toggleClass('active');
            var el_r = document.getElementById('sidebarCollapse_r');
            if (el_r.textContent == '«'){
                el_r.textContent = '»';
                el_r.setAttribute('title', 'Rechte Spalte zuklappen.');
            }else{
                el_r.textContent = '«';
                el_r.setAttribute('title', 'Rechte Spalte aufklappen.');
            }
        });
    });
