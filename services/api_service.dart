import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {

  static const String baseUrl =
      "https://success-point-backend.onrender.com";

  // -----------------------
  // BOOKS
  // -----------------------

  Future<List<dynamic>> getBooks() async {

    final response =
        await http.get(Uri.parse("$baseUrl/books"));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception("Failed to load books");
  }

  // -----------------------
  // CHAPTERS
  // -----------------------

  Future<List<dynamic>> getChapters(
      String bookId) async {

    final response = await http.get(
      Uri.parse(
        "$baseUrl/chapters/$bookId",
      ),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception("Failed to load chapters");
  }

  // -----------------------
  // CHAPTER CONTENT
  // -----------------------

  Future<List<dynamic>> getChapterContent(
      String chapterId) async {

    final response = await http.get(
      Uri.parse(
        "$baseUrl/chapter-content/$chapterId",
      ),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception(
      "Failed to load content",
    );
  }
}