using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddDescriptionColumns : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Description",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Description",
                table: "AudioFiles",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Description",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "Description",
                table: "AudioFiles");
        }
    }
}
