using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddAudioFileMetadata : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Album",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "AlbumArtist",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Artist",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "AudioMode",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "Bitrate",
                table: "AudioFiles",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "BpmTag",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "Channels",
                table: "AudioFiles",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Comment",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Composer",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Conductor",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "DiscNumber",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Genre",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "KeyTag",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Mp3Version",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "SampleRate",
                table: "AudioFiles",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Title",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "TrackNumber",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Year",
                table: "AudioFiles",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Album",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "AlbumArtist",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Artist",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "AudioMode",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Bitrate",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "BpmTag",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Channels",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Comment",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Composer",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Conductor",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "DiscNumber",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Genre",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "KeyTag",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Mp3Version",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "SampleRate",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Title",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "TrackNumber",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Year",
                table: "AudioFiles");
        }
    }
}
