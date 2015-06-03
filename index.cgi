#!/usr/bin/perl

#################################################################
# Media Stalker                                                 #
#################################################################
# Track your CDs/DVDs.                                          #
# http://sourceforge.net/projects/mediastalker                  #
#                                                               #
# Report Bugs/Suggestions to alasdair@alasdairkeyes.me.uk       #
# (C) 2008 Alasdair Keyes                                       #
#                                                               #
# Released under the same license as Perl itself                #
#################################################################

use strict;
use warnings;
use DBI;
use Data::Dumper;
use CGI;
use CGI::Session qw/-ip-match/;
use Mail::Sendmail;
use Digest::MD5 qw/md5_hex/;

##
## Setup
## You should only ever need to edit the next few lines
my $admin_password = "admin";
my $admin_email = 'email@address.com';
my $ms_path = "/mediastalker";
my $db = {
    server      => 'localhost',
    database    => 'mediastalkerdb',
    username    => 'mediastalker',
    password    => 'dbpassword',
    prefix      => 'ms_',
};
our $SENDMAIL_FLAG = 1; # Set to 0 to never send emails
##
## /Setup
##


### Subroutine to Send Emails
sub send_email {
    return unless ($SENDMAIL_FLAG); #Are we allowed to send emails
    my $email = shift || "";
    return if (!$email || $email eq 'email@address.com'); # return if we have no email address or it is the default email
    my $message = "You have had a request for someone to borrow an item of your media";
    my $subject = "MediaStalker - Borrow Request";
    my %mail =  (
            To      => $email,
            From    => $email,
            Message => $message,
            Subject => $subject,
        );
    sendmail(%mail) || return;
    return;
}


### Subroutine to format links to external sites
sub format_link_text {
    my $link_text = shift || return;
    $link_text =~ s/\s/\+/;
    $link_text =~ s/'/&#39;/;

    return $link_text; 
}


### Subroutine to fetch format types from DB
sub get_available_formats {
    my $dbh = shift;
    my $get_formats = $dbh->prepare("SELECT id, type FROM $db->{ prefix}format");
    $get_formats->execute();
    my $formats;
    while (my $row = $get_formats->fetchrow_hashref()) {
        $formats->{ $row->{ id } } =  $row->{ type };
    }
    return $formats;
}


### Subroutine to fetch available media from DB 
sub get_available_media {
    my $dbh = shift;
    my $get_media = $dbh->prepare("SELECT id, type FROM $db->{ prefix}media");
    $get_media->execute();
    my $media;
    while (my $row = $get_media->fetchrow_hashref()) {
        $media->{ $row->{ id } } =  $row->{ type };
    }
    return $media;
}

### Create own version of die as the regular one doesn't seem the like being called
### before headers are output, even when including CGI::header at the start of the die message,
### I guess it outputs other junk first (probably "\n", but haven't checked)
sub nice_die {
    my $message = shift || "";
    print $message;
    exit;
}


### Subroutine to fetch number of items we are managing
sub get_total_items {
    my $dbh = shift;
    my $get_total = $dbh->prepare("SELECT count(*) AS total_items FROM $db->{ prefix}item");
    $get_total->execute();
    my $total_items = 0;
    while (my $row = $get_total->fetchrow_hashref()) {
        $total_items =  $row->{ total_items };
    }
    return $total_items;
}




##
## Get CGI Params and setup general vars
##

my $cgi = new CGI;
my $mode = $cgi->param('mode') || "";

## Sometimes the mode is set by clicking a particular button
$mode = "edit" if ($cgi->param('edit_item'));
$mode = "delete" if ($cgi->param('delete_item'));
$mode = "view" if ($cgi->param('deny_delete'));

my $item = $cgi->param('item') || "";
$item = "" if ($item !~ /^\d+$/);
my $order_by = $cgi->param('orderby') || "artist";
$order_by = "artist" if ($order_by !~ /^(title|format|type|borrower_name)$/i);
my $asc = $cgi->param('asc') || "asc";
my $rev_asc = "asc";
$rev_asc = "desc" if ($asc eq "asc");
$asc = "asc" if ($asc !~ /^desc$/i);
my $borrow_id = $cgi->param('borrow_id') || "";
$borrow_id = "" if ($borrow_id !~ /^\d+$/);
my $borrow_status = $cgi->param('borrow_status') || "";
$borrow_status = "" if ($borrow_status !~ /^\w+$/);
my $error = "";
my $message = "";
my $version = '0.1.2';




##
## Header and footer templates
##

my $header = <<EOF;
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-Transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    <head>
        <title>Media Stalker v$version</title>
        <link rel='stylesheet' href='ms.css' type='text/css' title='MediaStalker' />
    </head>
    <body>
        <div id='page'>
            <div id='header'>
                <h3>MediaStalker v$version</h3>
                <p>Keep track of your media to the ends of the ether</p>
            </div>
            <div id='main'>
EOF
my $footer = <<EOF;
            </div>
        </div>
    </body>
</html>
EOF




##
## Initialise DB connection
##
my $dbh = DBI->connect("DBI:mysql:database=$db->{ database }:hostname=$db->{ server }", $db->{ username }, $db->{ password }, { PrintError  => 0 }
                    ) || nice_die ($cgi->header() . "Could not connect to database: $DBI::errstr");




##
## Session & Login Setup
##
my $sid = $cgi->cookie("MediaStalker") || undef;
my $session = new CGI::Session(undef, $sid, {Directory=>'/tmp'});
$session->name("MediaStalker");
$session->expire("+1h"); # Session timeout refreshes for 1hour
my $username = $session->param("username") || "Visitor";

my $sessionid = $session->id();


if ($cgi->param('submit_login') && $username eq "Visitor") {
    my $temp_user = $cgi->param('username') || "";
    my $temp_pass = $cgi->param('password') || "";
    if (!$temp_user) { 
        $error = "Please enter a username";
    } elsif (!$temp_pass) {
        $error = "Please enter a password";
    } elsif (($temp_user && $temp_user eq "admin") && ($temp_pass && $temp_pass eq $admin_password)) {
        #Login OK
        $username='admin';
        $session->param("username", $username);
        $message = "You are logged in as admin";
    } else {
        $error = "Login incorrect";
    }
}

if ($mode eq 'logout') {
    # Logout
    $username = "Visitor";
    $session->delete();
    $message = "You have logged out successfully";
}


my $cookie = $cgi->cookie(MediaStalker => $session->id);
#print $cgi->header( -cookie=>$cookie );




### Load Formate, media and total items
my $media = get_available_media($dbh);
my $formats = get_available_formats($dbh);
my $total_items = get_total_items($dbh);


##
## Updates to borrowed statuses can be called from many different modes, so we do these before
## the main processing
##
if ( ( $borrow_status =~ /^(returned|cancelled)$/ || ($borrow_status eq "borrowed" && $item)) && $borrow_id && $username eq "admin") {
    my $sql;
    if ($borrow_status eq "returned") {
        $sql = "UPDATE $db->{ prefix }borrow SET status='returned', returned_date=NOW() WHERE id=? and status='borrowed'";
    } elsif ($borrow_status eq "borrowed") {
        # Check that item isn't already lent out
        my $check_item_borrow_status = $dbh->prepare("SELECT $db->{ prefix }borrow.id FROM $db->{ prefix }borrow WHERE item_id=? AND status='borrowed'");
        $check_item_borrow_status->execute($item);
        if ($check_item_borrow_status->rows() == 0) {
            $sql = "UPDATE $db->{ prefix }borrow SET status='borrowed', borrowed_date=NOW() WHERE id=? and status='requested'";
        } elsif ($check_item_borrow_status->rows() == 1)  {
            $error = "This item has already been lent out";
        } else {
            $error = "There seems to be a database error, perhaps this item has already been lent out to 2 or more people at the same time"
        }
    } elsif ($borrow_status eq "cancelled") {
        $sql = "UPDATE $db->{ prefix }borrow SET status='cancelled' WHERE id=? AND status='requested'";
    }

    if ($sql) {
        my $borrow_update = $dbh->prepare($sql);
        $borrow_update->execute($borrow_id);
        if ($borrow_update->rows() != 1) {
            $error = "Couldn't update borrowed status";
        } else {
            $message = "Updated borrowed status to '$borrow_status'";
        }
    }
}



##
## General Stuff
##
my $content;
if (($mode eq 'view' || ($mode eq "delete" && $username eq "admin") ) && $item) {
    ### Selected to view a specific item



    ### Get this item
    my $get_title = $dbh->prepare("SELECT $db->{ prefix}item.id, $db->{ prefix}item.title, $db->{ prefix}item.artist, $db->{ prefix}item.information, $db->{ prefix}item.type, $db->{ prefix}item.format, $db->{ prefix}item.number_of_media FROM $db->{ prefix}item WHERE id=?");
    $get_title->execute($item);

    my $borrowed_name = "No";
    if ($get_title->rows() == 1) {
        $content .= "<table class='view'>";
        my ($viewing_artist);
        while (my $row = $get_title->fetchrow_hashref()) {
            $viewing_artist = $row->{ artist };
            my ($artist_link, $title_link);
            if ($media->{ $row->{ type } } =~ /^Music$/) {
                $artist_link = format_link_text($row->{ artist });
                $title_link = format_link_text($row->{ title });
            }
            $content .= "\n\t<tr>\n\t\t<th>id</th><td>$row->{ id }</td>\n\t</tr>";
            if ($artist_link) {
                $content .= "\n\t<tr>\n\t\t<th>Artist</th><td><a href='http://last.fm/music/$artist_link' target='_blank'>$row->{ artist }</a></td>\n\t</tr>";
            } else {
                $content .= "\n\t<tr>\n\t\t<th>Artist</th><td>$row->{ artist }</td>\n\t</tr>";
            }
            if ($title_link && $artist_link) {
                $content .= "\n\t<tr>\n\t\t<th>Title</th><td><a href='http://last.fm/music/$artist_link/_/$title_link' target='_blank'>$row->{ title }</a></td>\n\t</tr>";
            } else {
                $content .= "\n\t<tr>\n\t\t<th>Title</th><td>$row->{ title }</td>\n\t</tr>";
            }
            $content .= "\n\t<tr>\n\t\t<th>Format</th><td>$formats->{ $row->{ format } }</td>\n\t</tr>";
            $content .= "\n\t<tr>\n\t\t<th>Information</th><td>". ($row->{ information } || "---")."</td>\n\t</tr>";
            $content .= "\n\t<tr>\n\t\t<th>Media</th><td>$media->{ $row->{ type } }</td>\n\t</tr>";
            $content .= "\n\t<tr>\n\t\t<th>Number of Media</th><td>$row->{ number_of_media }</td>\n\t</tr>";

            my $get_borrowed_status=$dbh->prepare("SELECT $db->{ prefix }borrow.borrower_name FROM $db->{ prefix }borrow WHERE $db->{ prefix }borrow.item_id=? AND $db->{ prefix }borrow.status='borrowed' limit 1");
            $get_borrowed_status->execute($item);
            while (my $borrow_row = $get_borrowed_status->fetchrow_hashref()) {
                $borrowed_name = $borrow_row->{ borrower_name }
            }
            $content .= "\n\t<tr>\n\t\t<th>Borrowed?</th><td>$borrowed_name</td>\n\t</tr>";
        }
        if ($username eq "admin" && ($mode eq "view" || ($mode eq "delete" && $borrowed_name ne "No" ) ) ) {
            $content .= "\n\t<tr>\n\t\t<td colspan='2'><br/><form method='post' action='index.cgi'><input type='hidden' name='item' value='$item'/><input type='submit' name='edit_item' value='Edit Item'/>&nbsp;<input type='submit' name='delete_item' value='Delete'/></form><br/></td>\n\t</tr>";
            $error = "This item cannot be deleted until it has been returned from $borrowed_name" if ($borrowed_name ne "No" && $mode eq "delete");
        } elsif ($username eq "admin" && $mode eq "delete") {
            $content .= "\n\t<tr>";
            $content .= "\n\t\t<td colspan='2'></td>";
            $content .= "\n\t</tr>";
            $content .= "\n\t<tr>";
            $content .= "\n\t\t<td colspan='2'><span id='message'>Are you sure you wish to Delete this item?</span></td>";
            $content .= "\n\t</tr>";
            $content .= "\n\t<tr>";
            $content .= "\n\t\t<td colspan='2'>";
            $content .= "\n\t\t\t<br/><form method='post' action='index.cgi'><input type='hidden' name='item' value='$item'/><input type='submit' name='confirm_delete' value='Yes'/>&nbsp;<input type='submit' name='deny_delete' value='No'/></form><br/>";
            $content .= "</td>";
            $content .= "\n\t</tr>"; 
        }

        $content .= "</table><br/>";
   

        # Borrowing

        if ($cgi->param('borrow_submit') && $username eq "Visitor") {
            my $borrow_name = $cgi->param('borrow_name') || "";
            $borrow_name =~ s/\W//g;
            if (!$borrow_name) {
                $content .= "<div id='error'>Please Enter your name, you can only enter alpha-numeric characters</div>";
            } else {
                # Check if borrowed_name has already requested a borrowing request
                my $check_borrowing = $dbh->prepare("SELECT id FROM $db->{ prefix }borrow WHERE borrower_name=? AND (status='requested' OR status='borrowed') AND item_id=?");
                $check_borrowing->execute($borrow_name, $item);
                if (!$check_borrowing->rows()) {
                    # Nothing found
                    my $create_borrow_request = $dbh->prepare("INSERT INTO $db->{ prefix }borrow SET item_id=?, borrower_name=?, requested_date=now(), status='requested'");
                    $create_borrow_request->execute($item, $borrow_name);
                    if ($create_borrow_request->rows()) {
                        send_email($admin_email);
                        $content .= "<div id='message'>Your borrowing request has been submitted</div><br/>";
                    }
                } else {
                    $content .= "<div id='error'>You have already submitted a request to borrow this item</div><br/>";
                }
            }
        }
        if ($mode eq "view" || ($mode eq "delete" && $username eq "admin")) {
            if ($username eq "admin") {
                # Get borrow requests and information.
                my $get_borrow_info = $dbh->prepare("SELECT * FROM $db->{ prefix }borrow WHERE item_id=?");
                $get_borrow_info->execute($item);
                $content .= "<h3>Borrow information for this item</h3><table>";
                $content .= "<tr><th>Borrower</th><th>Status</th><th>Requested Date</th><th>Borrowed Date</th><th>Returned Date</th><th>Action</th></tr>";
                if ($get_borrow_info->rows()) {
                    while (my $row = $get_borrow_info->fetchrow_hashref()) {
                        $content .= "<tr>";
                        $content .= "<td>$row->{ borrower_name }</td><td>$row->{ status }</td><td>$row->{ requested_date }</td><td>" . ($row->{ borrowed_date } || '--') . "</td><td>" . ($row->{ returned_date } || '--' ) . "</td>";
                        $content .= "<td>";
                        if ($row->{ status } eq "requested" ) {
                            $content .= "<a href='index.cgi?mode=view;item=$item;borrow_status=borrowed;borrow_id=$row->{ id }'><img src='images/borrow.gif' alt='Borrow icon' title='Lend this item to $row->{ borrower_name }' border='0'/></a>";
                            $content .= "<a href='index.cgi?mode=view;item=$item;borrow_status=cancelled;borrow_id=$row->{ id }'><img src='images/cancel.gif' alt='Delete icon' title='Cancel Request' border='0'/></a>";
                        } elsif ($row->{ status } eq "borrowed") {
                            $content .= "<a href='index.cgi?mode=view;item=$item;borrow_status=returned;borrow_id=$row->{ id }'><img src='images/return.gif' alt='Return icon' title='Mark this item as returned from $row->{ borrower_name }' border='0'/></a>";
                        }
                        $content .= "</td>";
                        $content .= "</tr>";
                    }
                } else {
                    $content .= "<tr><td colspan='5'>There have been no requests to borrow this item.</td></tr>";
                }
                $content .= "</table>";
                
            } else {
                # Or if you're a Visitor, just show the borrow request
                $content .= "If you would like to borrow this item, please Enter your name and then submit";
                $content .= "<br/><form method='post' action='index.cgi'>";
                $content .= "<input type='hidden' name='mode' value='view'/>";
                $content .= "<input type='hidden' name='item' value='$item'/>";
                $content .= "<input type='text' name='borrow_name' size='50'/> <input type='submit' name='borrow_submit' value='Request to Borrow This Item'/>";
                $content .= "</form>";
            }


            # Get stuff by the same artist
            my $get_similar = $dbh->prepare("SELECT id, title, type, format FROM $db->{ prefix }item WHERE artist=? AND id !=? ");
            $get_similar->execute($viewing_artist, $item);
       
            if ($get_similar->rows() >= 1) {
                $content .= "<br/><h3>Other items by $viewing_artist...</h3>"; 
                $content .= "<table>\n\t<tr>\n\t\t<th>Title</th>\n\t\t<th>Type</th>\n\t\t<th>Format</th>\n\t</tr>";
                while (my $row=$get_similar->fetchrow_hashref()) {
                    $content .= "\n\t<tr>\n\t\t<td><a href='index.cgi?mode=view;item=$row->{ id }'>$row->{ title }</a></td>\n\t\t<td>$media->{ $row->{ type } }</td>\n\t\t<td>$formats->{ $row->{ format } }</td>\n\t</tr>";
                }
                $content .= "</table>";
            }
        }


    } else {
        $error = "Cannot find this item";
        $content .= "<a href='index.cgi'>Back to List</a>";
    }


##
## Show login page
## 

} elsif ( $username eq "Visitor" && ($mode eq 'login' || $cgi->param('submit_login'))) {

    $content .= "<div id='loginarea'><form method='post' action='.'>
    Username: <input type='text' name='username' size='20'/><br/><br/>
    Password: <input type='password' name='password' size='20'/><br/><br/>
    <input type='submit' name='submit_login' value='Login'/>&nbsp;<input type='submit' name='main' value='Back to Site'/>
    </form></div>";


##
## Show Search Related Pages
##

} elsif ( $mode eq "search" ) {

    # Search the database

    my @search_choices = ('artist','title','type','format');
    my $searching;

    foreach my $search_choice (@search_choices) {
        $searching->{ "search_$search_choice" } = $cgi->param("search_$search_choice") || "";
    }

    $content .= "<div id='searchbox'>";
    $content .= "\n\t\t\t<h3>Search</h3>";
    $content .= "\n\t\t\t<form method='post' action='.'>";
    $content .= "\n\t\t\t\t<input type='hidden' name='mode' value='search'/>";
    $content .= "\n\t\t\t\tArtist: <input type='text' size='30' name='search_artist' value='$searching->{ search_artist }'/><br/><br/>";
    $content .= "\n\t\t\t\tTitle: <input type='text' size='30' name='search_title' value='$searching->{ search_title }'/><br/><br/>";
    $content .= "\n\t\t\t\tType: <select name='search_type'>";
    $content .= "\n\t\t\t\t\t<option value=''>All</option>";
    foreach my $media_type (keys %$media) {
        $content .= "\n\t\t\t\t\t<option value='$media_type'";
        $content .= " selected='selected'" if ($searching->{ search_type } eq $media_type);
        $content .= ">$media->{ $media_type }</option>";
    }
    $content .= "\n\t\t\t\t</select><br/><br/>";
    $content .= "\n\t\t\t\tFormat: <select name='search_format'>";
    $content .= "\n\t\t\t\t\t<option value=''>All</option>";
    foreach my $format (keys %$formats) {
        $content .= "\n\t\t\t\t\t<option value='$format'";
        $content .= " selected='selected'" if ($searching->{ search_format } eq $format);
        $content .= ">$formats->{ $format }</option>";
    }
    $content .= "\n\t\t\t\t</select><br/><br/>";
    $content .= "\n\t\t\t\tSearch Method: <select name='search_method'>";
    $content .= "\n\t\t\t\t\t<option value='strict'>Strict</option>";
    $content .= "\n\t\t\t\t\t<option value='sloppy'";
    $content .= " selected='selected'" if ($cgi->param('search_method') && $cgi->param('search_method') eq "sloppy");
    $content .= ">Sloppy</option>";
    $content .= "\n\t\t\t\t</select><br/><br/>";
    $content .= "\n\t\t\t\t<input type='submit' name='search_submit' value='Search'/>";
    $content .= "\n\t\t\t</form>";
    $content .= "\n\t\t</div>\n";

    if ($cgi->param('search_submit')) {
        $content .= "\n\t\t<h3>Search Results</h3>";
        $content .= "\n\t\t<table>";
        $content .= "\n\t\t\t<tr>
        \t\t\t<th>Artist</th>
        \t\t\t<th>Title</th>
        \t\t\t<th>Type</th>
        \t\t\t<th>Format</th>
        \t\t</tr>";

        my $get_items_sql = "SELECT $db->{ prefix }item.id, $db->{ prefix }item.title, $db->{ prefix }item.artist, $db->{ prefix }item.information, $db->{ prefix }item.type, $db->{ prefix }item.format, $db->{ prefix }item.number_of_media FROM $db->{ prefix }item WHERE";

        my $and_check = 0;
        my @mysql_checks;
        foreach my $search_choice (@search_choices) {
            next if (!$searching->{ "search_$search_choice" });
            $get_items_sql .= " AND" if ($and_check);
            if ($cgi->param('search_method') eq "sloppy") {
                $get_items_sql .= " $search_choice like ?";
                my $search_data = $searching->{ "search_$search_choice" };
                push (@mysql_checks, ("%" . $search_data . "%"));
            } else {
                $get_items_sql .= " $search_choice=?";
                push (@mysql_checks, $searching->{ "search_$search_choice" });
            }
            $and_check++;
        }
        if (scalar(@mysql_checks)) {
            $get_items_sql .= " ORDER BY artist ASC";

            my $get_items = $dbh->prepare($get_items_sql);
            $get_items->execute(@mysql_checks);
            while (my $row=$get_items->fetchrow_hashref()) {
                $content .= "\n\t\t\t<tr>\n\t\t\t\t<td>$row->{ artist }</td>\n\t\t\t\t<td><a href='index.cgi?mode=view;item=$row->{ id }'>$row->{ title }</a></td>\n\t\t\t\t<td>$media->{ $row->{ type } }</td>\n\t\t\t\t<td>$formats->{ $row->{ format } }</td>\n\t\t\t</tr>\n";
            }
            $content .= "\n\t\t\t<tr>\n\t\t\t\t<td colspan='4'>No results found</td>\n\t\t\t</tr>" if (!$get_items->rows());
        }
        $content .= "\n\t\t</table>";

    }


##
## Editing Items
##

} elsif ($mode eq "edit" && $username eq "admin" && $item) {

    ### Get this item
    my $get_title = $dbh->prepare("SELECT $db->{ prefix}item.id, $db->{ prefix}item.title, $db->{ prefix}item.artist, $db->{ prefix}item.information, $db->{ prefix}item.type, $db->{ prefix}item.format, $db->{ prefix}item.number_of_media FROM $db->{ prefix}item WHERE $db->{ prefix}item.id=?");
    $get_title->execute($item);

    if ($get_title->rows() == 1) {

        my $loaded_item = $get_title->fetchrow_hashref();

        my @edit_choices = ('artist','title','type','format','number_of_media','information');
        my $editing;

        foreach my $edit_choice (@edit_choices) {
            if ($cgi->param('edit_submit') ) {
                $editing->{ "edit_$edit_choice" } = $cgi->param("edit_$edit_choice") || "";
            } else {
                $editing->{ "edit_$edit_choice" } = $loaded_item->{ $edit_choice } || "";
            }
            # Should be the only sanitization needed, to stop html display breaking, rest will be sanitized by DBI placeholders
            $editing->{ "edit_$edit_choice" } =~ s/"/'/g;
            if ($editing->{ "edit_$edit_choice" } eq "" && $edit_choice ne "information") {
                my $field_name = $edit_choice;
                $field_name =~ s/_/ /g;
                $error = "Please enter the " . $field_name;
            }
        }


        if ($cgi->param('edit_submit')) {
            ## Save the updated information

            if ($editing->{ edit_title } && $editing->{ edit_artist } && $editing->{ edit_type } && $editing->{ edit_format } && $editing->{ edit_number_of_media }) {
                my $edit_item = $dbh->prepare("UPDATE $db->{ prefix }item SET title=?, artist=?, type=?, format=?, number_of_media=?, information=? WHERE id=?");
                $edit_item->execute($editing->{ edit_title }, $editing->{ edit_artist }, $editing->{ edit_type }, $editing->{ edit_format }, $editing->{ edit_number_of_media }, $editing->{ edit_information }, $item);
                if ($edit_item->rows() == 1) {
                    $message = "Updated item succesfully";
                    print $cgi->redirect("$ms_path/index.cgi?mode=view;item=$item");
                } else {
                    $error = "Failed to update item, id not have the required number of parameters.";
                }
            }

        } elsif ($cgi->param('edit_cancel')) {
            # Back to main view
            print $cgi->redirect("$ms_path/index.cgi?mode=view;item=$item");
            
        }


        $content .= "<div id='addbox'>";
        $content .= "\n\t\t<h3>Edit Item</h3>";
        $content .= "<form method='post' action='.'>";
        $content .= "<input type='hidden' name='mode' value='edit'/>";
        $content .= "<input type='hidden' name='item' value='$item'/>";
        $content .= "Title: <input type='text' name='edit_title' value=\"$editing->{ edit_title }\" size='30'/><br/><br/>";
        $content .= "Artist/Director: <input type='text' name='edit_artist' value=\"$editing->{ edit_artist }\" size='30'/><br/><br/>";

        $content .= "Type: <select name='edit_type'>";
        foreach my $media_type (keys %$media) {
            $content .= "<option value='$media_type'";
            $content .= " selected='selected'" if ($editing->{ edit_type } eq $media_type);
            $content .= ">$media->{ $media_type }</option>\n";
        }
        $content .= "</select><br/><br/>";
        $content .= "Format: <select name='edit_format'>";
        foreach my $format (keys %$formats) {
            $content .= "<option value='$format'";
            $content .= " selected='selected'" if ($editing->{ edit_format } eq $format);
            $content .= ">$formats->{ $format }</option>\n";
        }
        $content .= "</select>";
        $content .= " Number of Media: <select name='edit_number_of_media'>";
        for (my $media_counter = 1; $media_counter <=20; $media_counter++) {
            $content .= "<option value='$media_counter'";
            $content .= " selected='selected'" if ($editing->{ edit_number_of_media } eq $media_counter);
            $content .= ">$media_counter</option>";
        }
        $content .= "</select><br/><br/>";
        $content .= "Information:<br/><textarea name='edit_information' rows='4' cols='30'>$editing->{ edit_information }</textarea><br/><br/>";

        $content .= "<input type='submit' name='edit_submit' value='Update item'/>&nbsp";
        $content .= "<input type='submit' name='edit_cancel' value='Cancel'/>";

        $content .= "</form";
        $content .= "</div>";

    } else {
        $error ="Cannot find this item";
        $content .= "<a href='index.cgi'>Back to List</a>";
    }


##
## Borrowing Reports
##

} elsif ($mode eq "borrow_report" && $username eq "admin") {

    # Show borrowed items

    my $get_borrowed = $dbh->prepare("SELECT $db->{ prefix }borrow.id AS borrow_id, $db->{ prefix }borrow.item_id, $db->{ prefix }borrow.borrower_name, $db->{ prefix }borrow.borrowed_date, $db->{ prefix }borrow.requested_date, $db->{ prefix }borrow.returned_date, $db->{ prefix }borrow.status, $db->{ prefix }item.artist, $db->{ prefix }item.title, $db->{ prefix }item.type, $db->{ prefix }item.format FROM $db->{ prefix }borrow LEFT JOIN $db->{ prefix }item ON $db->{ prefix }item.id=$db->{ prefix }borrow.item_id");
    $get_borrowed->execute();

    my @borrowed_statuses = ('borrowed','requested','returned','cancelled');
    my $report;
    my @values = ('item_id','borrow_id','borrower_name','borrowed_date','requested_date','returned_date','status','artist','title','type','format');

    if ($get_borrowed->rows()) {
        while ( my $row = $get_borrowed->fetchrow_hashref()) {
            foreach my $value (@values) {
                $report->{ $row->{ status } }{ $row->{ borrow_id } }{ $value } = $row->{ $value };
            }
        }
    }

    foreach my $borrowed_status (@borrowed_statuses) {
        $content .= "<h3>" . ucfirst($borrowed_status) . " Items</h3>\n";
        $content .= "<table>\n\t";
        if ($borrowed_status eq "borrowed") {
            $content .= "<tr>\n\t\t<th>Artist</th>\n\t\t<th>Title</th>\n\t\t<th>Type</th>\n\t\t<th>Format</th>\n\t\t<th>Borrowed By</th>\n\t\t<th>Borrowed On</th>\n\t\t<th>Actions</th>\n\t</tr>\n\t";
        } elsif ($borrowed_status eq "requested") {
            $content .= "<tr>\n\t\t<th>Artist</th>\n\t\t<th>Title</th>\n\t\t<th>Type</th>\n\t\t<th>Format</th>\n\t\t<th>Requested By</th>\n\t\t<th>Requested On</th>\n\t\t<th>Actions</th>\n\t</tr>\n\t";
        } elsif ($borrowed_status eq "returned") {
            $content .= "<tr>\n\t\t<th>Artist</th>\n\t\t<th>Title</th>\n\t\t<th>Type</th>\n\t\t<th>Format</th>\n\t\t<th>Borrowed By</th>\n\t\t<th>Returned On</th>\n\t\t<th>Actions</th>\n\t</tr>\n\t";
        } elsif ($borrowed_status eq "cancelled") {
            $content .= "<tr>\n\t\t<th>Artist</th>\n\t\t<th>Title</th>\n\t\t<th>Type</th>\n\t\t<th>Format</th>\n\t\t<th>Requested By</th>\n\t\t<th>Borrowed On</th>\n\t\t<th>Actions</th>\n\t</tr>\n\t";
        }
        foreach my $borrowed_items (keys %{$report->{ $borrowed_status }} ) {
            $content .= "<tr>\n\t\t";
            $content .= "<td><a href='index.cgi?mode=view;item=$report->{ $borrowed_status }{ $borrowed_items }{ item_id }' target='_blank'>$report->{ $borrowed_status }{ $borrowed_items }{ artist }</a></td>\n\t\t";
            $content .= "<td><a href='index.cgi?mode=view;item=$report->{ $borrowed_status }{ $borrowed_items }{ item_id }' target='_blank'>$report->{ $borrowed_status }{ $borrowed_items }{ title }</a></td>\n\t\t";
            $content .= "<td>$media->{ $report->{ $borrowed_status }{ $borrowed_items }{ type } }</td>\n\t\t";
            $content .= "<td>$formats->{ $report->{ $borrowed_status }{ $borrowed_items }{ format } }</td>\n\t\t";
            $content .= "<td>$report->{ $borrowed_status }{ $borrowed_items }{ borrower_name }</td>\n\t\t";
            if ($borrowed_status =~ /^(borrow|return|request)ed$/) {
                $content .= "<td>" . $report->{ $borrowed_status }{ $borrowed_items }{ $borrowed_status . "_date" } . "</td>\n\t";
            } else {
                $content .= "<td>$report->{ $borrowed_status }{ $borrowed_items }{ requested_date }</td>\n\t";
            }

            if ($borrowed_status eq "borrowed") {
                $content .= "<td><a href='index.cgi?borrow_id=$report->{ $borrowed_status }{ $borrowed_items }{ borrow_id };borrow_status=returned;mode=borrow_report'><img src='images/return.gif' alt='Return icon' title='Mark this item as returned from $report->{ $borrowed_status }{ $borrowed_items }{ borrower_name }' border='0'/></a></td>\n\t";
            } elsif ($borrowed_status =~ /^(return|cancell)ed$/) {
                $content .= "<td>&nbsp;</td>\n\t";
            } elsif ($borrowed_status eq "requested") {
                $content .= "<td><a href='index.cgi?borrow_id=$report->{ $borrowed_status }{ $borrowed_items }{ borrow_id };borrow_status=borrowed;mode=borrow_report;item=$report->{ $borrowed_status }{ $borrowed_items }{ item_id }'><img src='images/borrow.gif' alt='Borrow icon' title='Lend this item to $report->{ $borrowed_status }{ $borrowed_items }{ borrower_name }' border='0'/></a>&nbsp;<a href='index.cgi?borrow_id=$report->{ $borrowed_status }{ $borrowed_items }{ borrow_id };borrow_status=cancelled;mode=borrow_report'><img src='images/cancel.gif' alt='Cancel icon' title='Cancel Request' border='0'/></a></td>\n\t";
            }
            $content .= "</tr>\n";
        }
        $content .= "<tr><td colspan='7'>No Items $borrowed_status</td></tr>\n\t\t" if (scalar(keys %{$report->{ $borrowed_status }} ) == 0);
        $content .= "</table><p><br/><br/></p>";

    }


##
## Admin section - Update email addresses, passwords, etc
##

} elsif ($mode eq "admin" && $username eq "admin") {

    $content .= "<div id='adminbox'>";
    $content .= "\n\t\t\t<h3>Admin Area</h3>";
    $content .= "\n\t\t\t<p>";
    $content .= "\n\t\t\t<a href='index.cgi?mode=formats'>Manage format types</a><br/>";
    $content .= "\n\t\t\t<a href='index.cgi?mode=media'>Manage media types</a><br/>";
    $content .= "\n\t\t\t</p>";
    $content .= "\n\t\t</div>";




##
## Manage Media Types 
##

} elsif ($mode eq "media" && $username eq "admin") {

    # Add new media type
    if ($cgi->param('add_media')) {
        my $new_media_type = $cgi->param('new_media_type') || "";
        $new_media_type =~ s/(^\s+|\s+$)//g;

        if ($new_media_type) { 
            if (grep { $media->{ $_ } =~ /$new_media_type/i  } keys %$media) {
                $error = "There is already a media type called '$new_media_type'";
            } else {
                my $add_new_media = $dbh->prepare("INSERT into $db->{ prefix }media SET type=?");
                $add_new_media->execute($new_media_type);
                if ($add_new_media->rows() == 1) {
                    $message = "Added new type '$new_media_type'";
                    $media = get_available_media($dbh);
                } else {
                    $error = "Failed to add new type '$new_media_type'";
                }
            }
        } else {
            $error = "Please ensure you enter a new type";
        }
    }

    # Delete existing media type
    if (my $delete_media_id = $cgi->param('delete_media')) {
        if ($delete_media_id =~ /^\d+$/ && $delete_media_id > 4 && $media->{ $delete_media_id }) {
            my $check_media_use = $dbh->prepare("SELECT id FROM $db->{ prefix }item WHERE type=?");
            $check_media_use->execute($delete_media_id);
            if ($check_media_use->rows() > 0) {
                $error = "The media type '$media->{ $delete_media_id }' is still in use by " . $check_media_use->rows() . " items";
            } else {
                my $delete_media = $dbh->prepare("DELETE FROM $db->{ prefix }media WHERE id=?");
                $delete_media->execute($delete_media_id);
                if ($delete_media->rows() == 1) {
                    $message = "Media type '$media->{ $delete_media_id }' deleted succesfully";
                    $media = get_available_media($dbh);
                } else {
                    $error = "Unable to delete media type '$media->{ $delete_media_id }'";
                }
            }
        } else {
            $error = "Received invalid delete request";
        }
    } 

    $content .= "<div id='adminbox'>";
    $content .= "<h3>Media Types</h3>";
    $content .= "<p>Mediastalker can handle any number of media types, such as films, games, music, spoken word etc. You can add and remove custom types below.<br/></p>";
    $content .= "<form action='index.cgi' method='post'>";
    $content .= "<input type='hidden' name='mode' value='media'/>";
    $content .= "<table>";
    $content .= "<tr><th>Current Media Types</th><th>Action?</th></tr>";
    foreach my $media_type (keys %$media ) {
        $content .= "<tr>";
        $content .= "<td>$media->{ $media_type }</td>";
        if ($media->{ $media_type } =~ /^(Spoken Word|Film|Music|Game)$/) {
            $content .= "<td><img src='images/cancel-grey.png' alt='Cancel Icon - Greyed Out'/></td>";
        } else {
            $content .= "<td><a href='index.cgi?mode=media;delete_media=$media_type' title='Delete Media Type $media->{ $media_type }'><img src='images/cancel.gif' alt='Cancel Icon' border='0'/></a></td>";
        }
        $content .= "</tr>";
    }
    $content .= "<tr>";
    $content .= "<td><input type='text' name='new_media_type' size='25'/></td>";
    $content .= "<td><input type='submit' name='add_media' class='addbutton' value='.'/></td>";
    $content .= "</tr>";
    $content .= "</table>";
    $content .= "</form>";
    $content .= "<p><a href='index.cgi?mode=admin'>Back to Admin</a></p>";
    $content .= "</div>";




##
## Manage Formats
##

} elsif ($mode eq "formats" && $username eq "admin") {

    # Add new media type
    if ($cgi->param('add_format')) {
        my $new_format = $cgi->param('new_format') || "";
        $new_format =~ s/(^\s+|\s+$)//g;

        if ($new_format) {
            if (grep { $formats->{ $_ } =~ /$new_format/i  } keys %$formats) {
                $error = "There is already a format called '$new_format'";
            } else {
                my $add_new_format = $dbh->prepare("INSERT into $db->{ prefix }format SET type=?");
                $add_new_format->execute($new_format);
                if ($add_new_format->rows() == 1) {
                    $message = "Added new format '$new_format'";
                    $formats = get_available_formats($dbh);
                } else {
                    $error = "Failed to add new format '$new_format'";
                }
            }
        } else {
            $error = "Please ensure you enter a new format";
        }
    }


    # Delete existing media type
    if (my $delete_format_id = $cgi->param('delete_format')) {
        if ($delete_format_id =~ /^\d+$/ && $delete_format_id > 4 && $formats->{ $delete_format_id }) {
            my $check_format_use = $dbh->prepare("SELECT id FROM $db->{ prefix }item WHERE format=?");
            $check_format_use->execute($delete_format_id);
            if ($check_format_use->rows() > 0) {
                $error = "The format '$formats->{ $delete_format_id }' is still in use by " . $check_format_use->rows() . " items";
            } else {
                my $delete_format = $dbh->prepare("DELETE FROM $db->{ prefix }format WHERE id=?");
                $delete_format->execute($delete_format_id);
                if ($delete_format->rows() == 1) {
                    $message = "Format '$formats->{ $delete_format_id }' deleted succesfully";
                    $formats = get_available_formats($dbh);
                } else {
                    $error = "Unable to delete format '$formats->{ $delete_format_id }'";
                }
            }
        } else {
            $error = "Received invalid delete request";
        }
    }

    $content .= "<div id='adminbox'>";
    $content .= "<h3>Formats</h3>";
    $content .= "<p>Mediastalker can handle any number of formats such as CDs, DVDs, VHS, Cartridge etc. You can add and remove custom formats below.<br/></p>";
    $content .= "<form action='index.cgi' method='post'>";
    $content .= "<input type='hidden' name='mode' value='formats'/>";
    $content .= "<table>";
    $content .= "<tr><th>Current Formats</th><th>Action?</th></tr>";
    foreach my $format_type (keys %$formats ) {
        $content .= "<tr>";
        $content .= "<td>$formats->{ $format_type }</td>";
        if ($formats->{ $format_type } =~ /^(CD|DVD|VHS|Cartridge)$/) {
            $content .= "<td><img src='images/cancel-grey.png' alt='Cancel Icon - Greyed Out'/></td>";
        } else {
            $content .= "<td><a href='index.cgi?mode=formats;delete_format=$format_type' title='Delete Format $formats->{ $format_type }'><img src='images/cancel.gif' alt='Cancel Icon' border='0'/></a></td>";
        }
        $content .= "</tr>";
    }
    $content .= "<tr>";
    $content .= "<td><input type='text' name='new_format' size='25'/></td>";
    $content .= "<td><input type='submit' name='add_format' class='addbutton' value='.'/></td>";
    $content .= "</tr>";
    $content .= "</table>";
    $content .= "</form>";
    $content .= "<p><a href='index.cgi?mode=admin'>Back to Admin</a></p>"; 
    $content .= "</div>";


##
## Add a new item
##

} elsif ($mode eq "add" && $username eq "admin") {
  
    ## Add Item to the database

    my @add_choices = ('artist','title','type','format','number_of_media','information');
    my $adding;

    if ($cgi->param('new_submit')) {
        foreach my $add_choice (@add_choices) {
            $adding->{ "add_$add_choice" } = $cgi->param("add_$add_choice") || "";
            # Should be the only sanitization needed, to stop html display breaking, rest will be sanitized by DBI placeholders
            $adding->{ "add_$add_choice" } =~ s/"/'/g;
            if ($adding->{ "add_$add_choice" } eq "" && $add_choice ne "information") {
                my $field_name = $add_choice;
                $field_name =~ s/_/ /g;
                $error = "Please enter the " . $field_name;
            }
        }

        if ($adding->{ add_title } && $adding->{ add_artist } && $adding->{ add_type } && $adding->{ add_format } && $adding->{ add_number_of_media } ) {
            my $add_item = $dbh->prepare("INSERT INTO $db->{ prefix }item SET title=?, artist=?, type=?, format=?, number_of_media=?, information=?");
            $add_item->execute($adding->{ add_title }, $adding->{ add_artist }, $adding->{ add_type }, $adding->{ add_format }, $adding->{ add_number_of_media }, $adding->{ add_information });
            if ($add_item->rows() == 1) {
                $message = "Added item succesfully";
                $total_items = get_total_items($dbh);
                foreach my $key (keys %$adding) {
                    $adding->{ $key } = "";
                }
            } else {
                $error = "Failed to add item did not have all the required parameters.";
            }
            

        }
    }
 
    $content .= "<div id='addbox'>";
    $content .= "\n\t\t\t<h3>Add Item</h3>";
    $content .= "\n\t\t\t<form method='post' action='.'>";
    $content .= "\n\t\t\t\t<input type='hidden' name='mode' value='add'/>";
    $content .= "\n\t\t\t\tTitle: <input type='text' name='add_title' value='" . ($adding->{ add_title } || "") . "' size='30'/><br/><br/>";
    $content .= "\n\t\t\t\tArtist/Director: <input type='text' name='add_artist' value='" . ($adding->{ add_artist } || "") . "' size='30'/><br/><br/>";

    $content .= "\n\t\t\t\tType: <select name='add_type'>";
    foreach my $media_type (keys %$media) {
        $content .= "\n\t\t\t\t\t<option value='$media_type'";
        $content .= " selected='selected'" if ($adding->{ add_type } && $adding->{ add_type } eq $media_type);
        $content .= ">$media->{ $media_type }</option>";
    }
    $content .= "\n\t\t\t\t</select><br/><br/>";
    $content .= "\n\t\t\t\tFormat: <select name='add_format'>";
    foreach my $format (keys %$formats) {
        $content .= "\n\t\t\t\t\t<option value='$format'";
        $content .= " selected='selected'" if ($adding->{ add_format } && $adding->{ add_format } eq $format);
        $content .= ">$formats->{ $format }</option>";
    }
    $content .= "\n\t\t\t\t</select>";
    $content .= "\n\t\t\t\tNumber of Media: <select name='add_number_of_media'>";
    for (my $media_counter = 1; $media_counter <=20; $media_counter++) {
        $content .= "\n\t\t\t\t\t<option value='$media_counter'";
        $content .= " selected='selected'" if ($adding->{ add_number_of_media } && $adding->{ add_number_of_media } eq $media_counter);
        $content .= ">$media_counter</option>";
    }
    $content .= "\n\t\t\t\t</select><br/><br/>";
    $content .= "\n\t\t\t\tInformation:<br/><textarea name='add_information' rows='4' cols='30'></textarea><br/><br/>";

    $content .= "\n\t\t\t\t<input type='submit' name='new_submit' value='Add new item'/>";

    $content .= "\n\t\t\t</form>";
    $content .= "\n\t\t</div>";


##
## After all the other modes, we'll just process the main page
##
    
} else {

    if ($cgi->param('confirm_delete') && $username eq "admin" && $item) {
        my $delete_item = $dbh->prepare("DELETE FROM $db->{ prefix }item WHERE id=?");
        $delete_item->execute($item);
        
        if ($delete_item->rows() == 1) {
            $message = "Deleted Item Succesfully";
            $total_items = get_total_items($dbh);
        } elsif ($delete_item->rows() == 0) {
            $error = "Couldn't find the item to delete, perhaps it has been deleted already?";
        } else {
            $error = "Error deleting item: " . ( $dbh->errstr || "" );
        }
        
    }


    # Main page

    $content .= "<a id='top'/>\n";
    $content .= "<table>\n\t<tr>\n\t\t<th";
    $content .= " class='highlight'" if ($order_by =~ /^artist$/i);
    $content .= "><a href='index.cgi?orderby=artist;asc=$rev_asc'>Artist</a></th>\n\t\t<th";
    $content .= " class='highlight'" if ($order_by =~ /^title$/i);
    $content .= "><a href='index.cgi?orderby=title;asc=$rev_asc'>Title</a></th><th";

    $content .= " class='highlight'" if ($order_by =~ /^type$/i);
    $content .= "><a href='index.cgi?orderby=type;asc=$rev_asc'>Type</a></th>\n\t\t<th";

    $content .= " class='highlight'" if ($order_by =~ /^format$/i);
    $content .= "><a href='index.cgi?orderby=format;asc=$rev_asc'>Format</a></th>\n\t\t<th";

    $content .= " class='highlight'" if ($order_by =~ /^borrower_name$/i);
    $content .= "><a href='index.cgi?orderby=borrower_name;asc=$rev_asc'>Borrowed?</a></th>";
    $content .= "</tr>";

    my $get_items = $dbh->prepare("SELECT $db->{ prefix }item.id, $db->{ prefix }item.title, $db->{ prefix }item.artist, $db->{ prefix }item.information, $db->{ prefix }item.type, $db->{ prefix }item.format, $db->{ prefix }item.number_of_media, $db->{ prefix }borrow.borrower_name FROM $db->{ prefix }item left join $db->{ prefix }borrow ON $db->{ prefix }borrow.item_id = $db->{ prefix }item.id AND $db->{ prefix }borrow.status = 'borrowed' ORDER BY $order_by $asc");
    $get_items->execute();

    if ($get_items->rows() < 1) {
        $content .= "\n<tr>\n\t<td colspan='5'>No Items Found</td>\n</tr>";
    } else {
        while (my $row = $get_items->fetchrow_hashref()) {
            $row->{ artist } =~ s/\&/\&amp;/g;
            $row->{ title } =~ s/\&/\&amp;/g;
            $content .= "\n<tr>\n\t<td>$row->{ artist }</td>\n\t<td><a href='index.cgi?mode=view;item=$row->{ id }'>$row->{ title }</a></td>\n\t<td>$media->{ $row->{ type } }</td>\n\t<td>$formats->{ $row->{ format } }</td>\n\t<td>". ($row->{ borrower_name } || "&nbsp;") . "</td>\n</tr>";
        }
    }
    $content .= "\t\t\t\t</table>";
    $content .= "<a href='#top'>Back to Top</a>";
}
$content .= "<br/><h4>Media Stalker v$version - <a href='http://sourceforge.net/projects/mediastalker/'>http://sourceforge.net/projects/mediastalker/</a></h4>";

my $log_text = "<a href='index.cgi?mode=login'>Login</a><br/>";
if ($username eq "admin") {
    $log_text = "<a href='index.cgi?mode=logout'>Logout</a><br/><a href='index.cgi?mode=admin'>Admin Area</a><br/>";
    $log_text .= "<a href='index.cgi?mode=add'>Add new Item</a><br/>";
    $log_text .= "<a href='index.cgi?mode=borrow_report'>View Borrowed</a><br/>";
}

$content = "<br/><div id='error'>$error</div><br/>" . $content if ($error);
$content = "<br/><div id='message'>$message</div><br/>" . $content if ($message);






##
## Print all the output...
##
print $cgi->header( -cookie=>$cookie );
print $header;

## Menu
print <<EOF;
                <div id='menu'>
                    <div class='menuarea'>
                        Currently Stalking:<br/><b>$total_items items</b>
                    </div>
                    <div class='menuarea'>
                        <b>Logged in as:</b><br/>[ $username ]<br/>
                        $log_text
                    </div>
                    <div class='menuarea'>
                        <b>Menu</b><br/>
                        <a href='index.cgi'>Media List</a><br/>
                        <a href='index.cgi?mode=search'>Search</a><br/>
                    </div>
                    <p>
                        <a href="http://validator.w3.org/check?uri=referer"><img style="border:0;width:88px;height:31px" src="http://www.w3.org/Icons/valid-xhtml10" alt="Valid XHTML 1.0 Transitional" height="31" width="88" /></a><br/>
                        <a href="http://jigsaw.w3.org/css-validator/validator?uri=http://h4x0red.co.uk/h4x0red.css"><img style="border:0;width:88px;height:31px" src="http://jigsaw.w3.org/css-validator/images/vcss" alt="Valid CSS!" /></a>
                    </p>
                </div>
EOF

## Content
print <<EOF;
                <div id='content'>
                    $content
                </div>
EOF

## Footer
print $footer;
