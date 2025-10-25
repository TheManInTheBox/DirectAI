using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddGenerationMusicalParams : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "Parameters_Bars",
                table: "GenerationRequests",
                type: "integer",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Parameters_Key",
                table: "GenerationRequests",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Parameters_Scale",
                table: "GenerationRequests",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Parameters_SectionType",
                table: "GenerationRequests",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Parameters_TimeSignature",
                table: "GenerationRequests",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Parameters_Bars",
                table: "GenerationRequests");

            migrationBuilder.DropColumn(
                name: "Parameters_Key",
                table: "GenerationRequests");

            migrationBuilder.DropColumn(
                name: "Parameters_Scale",
                table: "GenerationRequests");

            migrationBuilder.DropColumn(
                name: "Parameters_SectionType",
                table: "GenerationRequests");

            migrationBuilder.DropColumn(
                name: "Parameters_TimeSignature",
                table: "GenerationRequests");
        }
    }
}
