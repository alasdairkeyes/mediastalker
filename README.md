# Mediastalker

Mediastalker lets you easily cataloge and manage your
CDs/DVDs/Videos/Games through a web-based front end allowing you to
add remove items and others to peruse your collection.

This project is old and has not been touched since 2008. It will not be updated.

## Installation

* Uncompress the installation files and upload them into the public area
of your website, this is often public_html/ or www/.

* If you're using Linux/Unix, set the permissions on the file to
`rwxr-xr-x (755)` this can often be done through an FTP client or by
running...

```
$ chmod 755 index.cgi
```

* Import the skeleton default database information.
If you have phpMyAdmin you can import the `createdbstructure.sql` file
in the usual way.
If you don't, you can do it manually by creating the database in
MySQL using

```
mysql> CREATE DATABASE mediastalkerdb;
mysql> GRANT ALL ON mediastalkerdb.* TO mediastalker@localhost IDENTIFIED BY 'mysecurepassword';
mysql> FLUSH PRIVILEGES;
```

Then from the command line run...

```
$ mysql -umediastalker -p mediastalkerdb < createdbstructure.sql
```

* Open up `index.cgi` and edit the following lines within the Setup section
at the top of the file...
 * `$admin_password` -> A password to login to MediaStalker
 * `$admin_email` -> Your email address
 * `$ms_path` -> Change this to the location of your MediaStalker
    installation if different from the default mediastalker folder.

* Update the database details within the `$db` variable for your database.

* Visit the page by visiting http://yourserver.net/mediastalker

The Login username is `admin`.
Password is whatever you set it to when editing the `index.cgi` file.


## Trouble Shooting

* If you get a 500 Internal Server Error upon viewing the script in 
a browser check the following...
 * Your Webserver can execute Perl CGI Scripts with .cgi extentions.
 * The index.cgi file has 755 permissions.
 * Your Webserver has the perl Mail::Sendmail module installed, if you don't
  you can get around this by commenting out the line
use Mail::Sendmail;
to 
```
# use Mail::Sendmail
```

and setting
```
$SENDMAIL_FLAG = 0;
```
So that the system doesn't attempt to send emails

## Licensing

MediaStalker is released under the GNU General Public License.
http://www.gnu.org/licenses/gpl.html
