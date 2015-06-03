-- MySQL dump 10.10
--
-- Host: localhost    Database: mediastalkerdb
-- ------------------------------------------------------
-- Server version	5.0.22

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ms_borrow`
--

DROP TABLE IF EXISTS `ms_borrow`;
CREATE TABLE `ms_borrow` (
  `id` int(10) unsigned NOT NULL auto_increment,
  `item_id` int(10) unsigned NOT NULL,
  `borrower_name` varchar(50) NOT NULL,
  `requested_date` datetime default NULL,
  `borrowed_date` datetime default NULL,
  `returned_date` datetime default NULL,
  `status` enum('requested','borrowed','returned','cancelled') NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

--
-- Table structure for table `ms_format`
--

DROP TABLE IF EXISTS `ms_format`;
CREATE TABLE `ms_format` (
  `id` int(10) unsigned NOT NULL auto_increment,
  `type` varchar(100) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

--
-- Dumping data for table `ms_format`
--

/*!40000 ALTER TABLE `ms_format` DISABLE KEYS */;
LOCK TABLES `ms_format` WRITE;
INSERT INTO `ms_format` VALUES (1,'CD'),(2,'DVD'),(3,'VHS'),(4,'Cartridge');
UNLOCK TABLES;
/*!40000 ALTER TABLE `ms_format` ENABLE KEYS */;


--
-- Table structure for table `ms_item`
--

DROP TABLE IF EXISTS `ms_item`;
CREATE TABLE `ms_item` (
  `id` int(10) unsigned NOT NULL auto_increment,
  `title` varchar(200) NOT NULL default 'New Item',
  `artist` varchar(200) NOT NULL default 'New Artist',
  `information` text,
  `type` int(10) unsigned NOT NULL,
  `format` int(10) unsigned NOT NULL,
  `number_of_media` int(10) unsigned NOT NULL default '1',
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

--
-- Table structure for table `ms_media`
--

DROP TABLE IF EXISTS `ms_media`;
CREATE TABLE `ms_media` (
  `id` int(10) unsigned NOT NULL auto_increment,
  `type` varchar(100) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

--
-- Dumping data for table `ms_media`
--


/*!40000 ALTER TABLE `ms_media` DISABLE KEYS */;
LOCK TABLES `ms_media` WRITE;
INSERT INTO `ms_media` VALUES (1,'Film'),(2,'Game'),(3,'Music'),(4,'Spoken Word');
UNLOCK TABLES;
/*!40000 ALTER TABLE `ms_media` ENABLE KEYS */;

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

