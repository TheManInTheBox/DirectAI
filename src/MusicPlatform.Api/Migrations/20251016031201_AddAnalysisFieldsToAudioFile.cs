using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddAnalysisFieldsToAudioFile : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<double>(
                name: "Bpm",
                table: "AudioFiles",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Key",
                table: "AudioFiles",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "TimeSignature",
                table: "AudioFiles",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Bpm",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "Key",
                table: "AudioFiles");

            migrationBuilder.DropColumn(
                name: "TimeSignature",
                table: "AudioFiles");
        }
    }
}
